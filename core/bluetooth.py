"""Bluetooth IO subsystem for the BioHarness."""

import sys
import time
import logging
import threading
from queue import Queue

import bluetooth

from .protocol import encode_message, MC, MI, Message, decode_bytestream

logger = logging.getLogger(__name__)

__all__ = ['BioharnessIO']


class BioharnessIO:

    def __init__(self, address='', port=1, lifesign_interval=2, reconnect=True,
                 daemon=False):
        """Handle message-level communication with a Bioharness device via BLE.

        Args:
            address: the MAC address of the device (if not provided, an attempt
              will be made to discover the device, which will take a few seconds)
            port: bluetooth port (typically 1)
            lifesign_interval: life-sign interval in seconds to keep connection
              up
            reconnect: attempt to reconnect on connection failure
            daemon: use a daemon thread
        """
        # BT MAC address of device
        if not address:
            address = self._discover()
        self._address = address
        self._port = port
        # whether we want to auto reconnect (eg after out of range)
        self._reconnect = reconnect
        # send "life signs" every this many seconds
        self._lifesign_interval = lifesign_interval
        # queue of Message objects to send to device
        self._send_queue = Queue()
        # queue of Message objects that we got from the device
        self._recv_queue = Queue()
        # set of reply messages that we're awaiting
        self._awaited_replies = {}
        # setting this to True causes the thread to eventually finish
        self._shutdown = False
        # transmission thread
        self._thread = threading.Thread(target=self._run, name='BHT-Xfer')
        self._thread.daemon = daemon
        self._thread.start()

    def shutdown(self):
        """Shut down the service (closes the socket and exits the thread)."""
        if not self._thread.is_alive():
            logger.warning("Already shut down.")
        else:
            logger.info("Shutting down BioHarness link...")
            self._shutdown = True
            self._thread.join()
            logger.info('Done.')

    def enqueue_message(self, msg):
        """Enqueue a new message to be sent to the device."""
        if isinstance(msg, MC) and msg in MC:
            # may pass in just the message identifier if no payload
            msg = Message(msgid=msg)
        self._send_queue.put(msg)

    @property
    def received_messages(self):
        """A queue of received messages that one can read from."""
        return self._recv_queue

    def _run(self):
        """Run function for internal service thread."""
        # reconnect loop
        while not self._shutdown:
            logger.info(f'Connecting to device {self._address}...')
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            try:
                sock.connect((self._address, self._port))
            except IOError:
                if self._reconnect:
                    logger.warning("Connection attempt failed, "
                                   "attempting reconnect...")
                    time.sleep(1)
                    continue
                else:
                    logger.error("Connetion attempt failed, stopping...")
                    self._shutdown = True
                    break
            logger.info('Connected; now transferring...')
            try:
                # run transmission loop and decode the resulting byte stream
                for msg in decode_bytestream(self._transmit_loop(sock)):
                    self._handle_message(msg)
            except RuntimeError:
                logger.info(f"Byte stream ended")
            except IOError as e:
                logger.error(f"Encountered IO error {e}")
                logger.info("Attempting to reconnect...")
            finally:
                logger.info('Transmission stopped; closing socket...')
                sock.close()
                logger.info('Socket closed.')

    def _handle_message(self, msg):
        """Handle a received message."""
        logger.debug("Decoded: %s", msg)
        self._recv_queue.put(msg)

    def _transmit_loop(self, sock):
        """Main data transmission loop. This function sends messages that have
        been enqueued via enqueue_msg()."""
        last_lifesign_sent_at = 0
        while not self._shutdown:
            # ensure that we're sending life signs at the appropriate interval
            t = time.time()
            if t - last_lifesign_sent_at > self._lifesign_interval:
                logger.debug("Sending life sign...")
                self._send_message(sock, Message(MI.Lifesign))
                last_lifesign_sent_at = 0

            # send off any new messages from the queue
            while not self._send_queue.empty():
                msg = self._send_queue.get()
                self._send_message(sock, msg)

            # get next data packet
            data = sock.recv(256)
            if data:
                logger.debug('received %d bytes of data (%s)', len(data), data)
            else:
                logger.debug('recv() returned no data.')

            # yield that in form of bytes
            for b in data:
                yield b

    # noinspection PyMethodMayBeStatic
    def _send_message(self, sock, msg):
        """Send a message and optional payload over the given socket."""
        raw = encode_message(msg)
        logger.debug('Sending %s (bytes %s).', msg, raw)
        sock.send(raw)

    # noinspection PyMethodMayBeStatic
    def _discover(self):
        """Attempt to discover the right device. Exit on failure."""
        # discover the device if no address provided
        logger.info("No BioHarness (BHT) device MAC address provided, "
                    "initiating discovery...")
        results = bluetooth.discover_devices(lookup_names=True)
        matches = [(addr, name) for addr, name in results
                   if name.startswith('BH') and 'BHT' in name]
        if not matches:
            logger.error("Found no applicable BHT device in range. Please "
                         "make sure that the device is turned on "
                         "(blinking). Exiting...")
            sys.exit(1)
        else:
            if len(matches) > 1:
                allmatches = '\n'.join([f'* {name} ({addr})'
                                        for addr, name in matches])
                logger.warning(f'Found more than one matching BHT device. '
                               f'Using the first one that was discovered:\n'
                               f'{allmatches}')
            address, withname = matches[0]
            logger.info(f"Discovered device {withname} ({address})")
        return address
