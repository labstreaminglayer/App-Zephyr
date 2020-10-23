"""Main class to interact with the BHT device."""

import logging
import queue
import asyncio
from concurrent import futures

from .bluetooth import BioharnessIO
from .protocol import Message, MI, periodic_messages, transmit_state2data_packet

logger = logging.getLogger(__name__)


class BioHarness:
    """Main class to interact with a BioHarness device."""

    def __init__(self, address='', *, port=1, timeout=20, loop=None):
        """Create a new BioHarness interface.

        Args:
            address: the bluetooth MAC address of the device, or empty if a
              device should be auto-discovered
            port: optionally the bluetooth port (usually 1)
            timeout: optionally a time out after which async commands expire
            loop: optionally override the event loop from which calls to this
              class are to be made (otherwise the currently running loop is used)

        """
        # dictionary that maps message types to queues of futures that will hold
        # the eventual result (the dictionary itself is immutable)
        self._awaited_messages = {mi: queue.Queue() for mi in MI}
        # dictionary of handlers that are invoked on streaming data packets
        self._streaming_handlers = {mi: None for mi in periodic_messages}
        self._timeout = timeout
        # get the event loop that we're interacting with
        self._loop = loop or asyncio.get_running_loop()
        # the module that does the actual data I/O
        self.io = BioharnessIO(address, port, daemon=True)
        self.io._handle_message = self._dispatch_message

    def shutdown(self):
        """Shut down the link."""
        self.io.shutdown()

    # --- various getters ---

    async def get_serial_number(self):
        """Retrieve the serial number of the device."""
        return (await self._call(MI.GetSerialNumber)).payload_str().strip()

    async def get_boot_software_version(self):
        """Retrieve the boot software version of the device."""
        return (await self._call(MI.GetBootSoftwareVersion)).payload

    async def get_application_software_version(self):
        """Retrieve the application software version of the device."""
        return (await self._call(MI.GetApplicationSoftwareVersion)).payload

    async def get_hardware_part_number(self):
        """Retrieve the hardware part number of the device."""
        return (await self._call(MI.GetHardwarePartNumber)).payload_str()

    async def get_bootloader_part_number(self):
        """Retrieve the bootloader part number of the device."""
        return (await self._call(MI.GetBootloaderPartNumber)).payload_str().strip()

    async def get_application_part_number(self):
        """Retrieve the application part number of the device."""
        return (await self._call(MI.GetApplicationPartNumber)).payload_str()

    async def get_unit_mac_address(self):
        """Retrieve the MAC address of the device."""
        return (await self._call(MI.GetUnitMACAddress)).payload_str()

    async def get_bluetooth_friendly_name(self):
        """Retrieve the friendly name of the device."""
        return (await self._call(MI.GetUnitBluetoothFriendlyName)).payload_str()

    async def get_network_id(self):
        """Retrieve the network ID of the device."""
        return (await self._call(MI.GetNetworkID)).payload_str()

    async def get_infos(self):
        """Get various pieces of queryable information as a dictionary."""
        infos = {
            'serial': self.get_serial_number(),
            'net_id': self.get_network_id(),
            'hw_part_no': self.get_hardware_part_number(),
            'mac_addr': self.get_unit_mac_address(),
            'app_part_no': self.get_application_part_number(),
            'app_sw_version': self.get_application_software_version(),
            'bt_friendly_name': self.get_bluetooth_friendly_name(),
            'boot_sw_ver': self.get_boot_software_version(),
            'bootloader_part_no': self.get_bootloader_part_number(),
        }
        results = await asyncio.gather(*infos.values())
        return {k: v for k, v in zip(infos.keys(), results)}

    # --- switches to enable/disable various kinds of data streams ---

    async def toggle_general(self, handler):
        """Toggle the general data on or off."""
        return await self._toggle_handler(MI.SetGeneralDataPacketTransmitState, handler)

    async def toggle_accel(self, handler):
        """Toggle the accelerometer data on or off."""
        return await self._toggle_handler(MI.SetAccelerometerPacketTransmitState, handler)

    async def toggle_accel100mg(self, handler):
        """Toggle the accelerometer data in units of 100mg on or off."""
        return await self._toggle_handler(MI.SetAccelerometer100mgPacketTransmitState, handler)

    async def toggle_breathing(self, handler):
        """Toggle the breathing data in units on or off."""
        return await self._toggle_handler(MI.SetBreathingWaveformPacketTransmitState, handler)

    async def toggle_ecg(self, handler):
        """Toggle the ECG data on or off."""
        return await self._toggle_handler(MI.SetECGWaveformPacketTransmitState, handler)

    async def toggle_rtor(self, handler):
        """Toggle the R-to-R data on or off."""
        return await self._toggle_handler(MI.SetRtoRDataPacketTransmitState, handler)

    async def toggle_summary(self, handler, ival=1):
        """Toggle the summary data and/or set the transmit and integration interval (in seconds)."""
        # noinspection PyTypeChecker
        return await self._toggle_handler(MI.SetSummaryDataPacketUpdateRate, handler,
                                          payload_on=[ival, 0], payload_off=[0, 0])

    async def toggle_events(self, handler):
        """Toggle the event handler."""
        self._streaming_handlers[MI.EventPacket] = handler
        return True

    # --- internal ---

    async def _toggle_handler(self, msgid, handler=None, payload_on=1, payload_off=0):
        """Enable/disable a handler for a given message id.

        Args:
            msgid: message ID to which we'd like to respond
            handler: the handler to enable, or None to disable
            payload_on: the payload to send if the handler is installed
            payload_off: the payload to send if the handler is removed

        Returns:
            the response message
        """
        try:
            # attempt to enable/disable the data stream (may throw if unsuccessful)
            resp = await self._call(msgid, payload_on if handler else payload_off)
            # update the handler if success
            packet_msg_type = transmit_state2data_packet[msgid]
            self._streaming_handlers[packet_msg_type] = handler
            return resp
        except:
            raise

    async def _call(self, msgid, payload=()):
        """Invoke a remote procedure call asynchronously and return the resulting
        message, throw a RuntimeError if the op failed or a TimeoutError if the
        operation timed out."""
        fut = self._loop.create_future()
        self._awaited_messages[msgid].put(fut)
        self._send(msgid, payload)
        try:
            await asyncio.wait_for(fut, self._timeout)
        except futures.TimeoutError:
            raise TimeoutError(f"Waiting for device response to {MI(msgid).name} timed out.")
        msg = fut.result()
        msg.ensure_fin_ok()
        return msg

    def _send(self, msgid, payload=()):
        """Short-hand to a message with some payload."""
        if not isinstance(payload, (list, tuple, bytes)):
            payload = [payload]
        self.io.enqueue_message(Message(msgid, payload))

    def _dispatch_message(self, msg):
        """Function to dispatch returned messages."""
        logger.debug(f"Received message: %s", msg)
        if msg.msgid in self._streaming_handlers:
            # periodic / streaming data
            handler = self._streaming_handlers[msg.msgid]
            if handler:
                self._loop.call_soon_threadsafe(handler, msg)
            else:
                logger.debug(f'Got {msg.msgid} but no handler is installed; discarding...')
        elif msg.msgid == MI.Lifesign:
            # nothing to do in response to life-sign messages
            pass
        else:
            # assume that this is a response to some command
            queue = self._awaited_messages[msg.msgid]
            if not queue.empty():
                # mark the next result for that queue as done
                fut = queue.get()
                self._loop.call_soon_threadsafe(fut.set_result, msg)
                logger.debug(f'marked future {id(fut)} done.')
            else:
                logger.warning(f"Got unrequested {msg}; discarding.")
