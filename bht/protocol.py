"""Protocol definitions for Zephyr BioHarness and byte stream encoding/decoding
logic."""

import enum
import math
import functools
import time
import datetime
import logging
import cbitstruct as bitstruct

from .bitcrunching import crc8, reverse_bits8

__all__ = ['MessageConstants', 'Message', 'MC', 'MI', 'encode_message',
           'decode_bytestream', 'periodic_messages', 'transmit_state2data_packet',
           'StreamingMessage', 'GeneralDataMessage', 'SummaryDataMessageV2',
           'SummaryDataMessageV3', 'WaveformMessage', 'ECGWaveformMessage',
           'BreathingWaveformMessage', 'Accelerometer100MgWaveformMessage',
           'AccelerometerWaveformMessage', 'RtoRMessage', 'EventMessage']

logger = logging.getLogger(__name__)


class MessageConstants(enum.IntEnum):
    # generic constants used in BHT framing protocol
    # start of text (first byte in a msg)
    STX = 0x02
    # end of text (last byte in a msg)
    ETX = 0x03
    # acknowledged
    ACK = 0x06
    # not acknowledged
    NAK = 0x15


class MessageIDs(enum.IntEnum):

    # --- periodic data packets sent by the device (once enabled) ---

    Lifesign = 0x23  # keepalive handshake message
    GeneralDataPacket = 0x20  # 53-byte payload with various slow changing parameters
    BreathingWaveformPacket = 0x21  # 32-byte payload incl. 18 samples with 56ms sampling interval, bit-packed
    ECGWaveformPacket = 0x22  # 88-byte payload incl. 63 samples of ECG (at 4ms sample interval)
    RtoRPacket = 0x24  # 45-byte payload incl. 18 samples of R-to-R data (56ms sample ival); 16bits
    AccelerometerPacket = 0x25  # 84-byte payload incl. 20 "sample sets" (20ms sample ival) X/Y/Z, 10bit, 15byte repeater
    BluetoothDeviceDataPacket = 0x27  # for 3rd party devices connected to the BioHarness
    ExtendedDataPacket = 0x28  # additional derived summary data
    Accelerometer100MgPacket = 0x2A  # accel in units of 1/10th of a g (otherwise encoded same I think)
    SummaryDataPacket = 0x2B  # 71-byte packet with various slow-changing params (heart rate etc) - byte 12 of the msg has the version
    EventPacket = 0x2C  # event code and optional event-specific data
    LoggingDataPacket = 0x3F  # if logging data were requested via send logging data
    LiveLogAccessDataPacket = 0x60  # if requersted by live log access message

    # --- commands ---

    # toggling various data streams (payload is 0 or 1)
    SetGeneralDataPacketTransmitState = 0x14        # every ~1000ms
    SetBreathingWaveformPacketTransmitState = 0x15  # every ~1000ms
    SetECGWaveformPacketTransmitState = 0x16        # every 250ms
    SetRtoRDataPacketTransmitState = 0x19           # every ~1000ms
    SetAccelerometerPacketTransmitState = 0x1E      # every 400ms
    SetAccelerometer100mgPacketTransmitState = 0xBC  # every 400ms
    SetExtendedDataPacketTransmitState = 0xB8  # bit mask of what data types to enable
    SetSummaryDataPacketUpdateRate = 0xBD  # payload is 2 bytes (ls/ms) for update period in sec.

    # queries (no payload unless otherwise noted)
    GetRTCDateTime = 0x08
    GetBootSoftwareVersion = 0x09
    GetApplicationSoftwareVersion = 0x0A
    GetSerialNumber = 0x0B  # returns a 12-byte payload str (BHT35435646)
    GetHardwarePartNumber = 0x0C  # returns 12-byte payload str (9900.0085v1a etc)
    GetBootloaderPartNumber = 0x0D  # returns a 12-byte payload str (similar to hw part no)
    GetApplicationPartNumber = 0x0E  # returns a 12-byte payload str
    GetUnitMACAddress = 0x12  # returns a 17-byte payload str
    GetUnitBluetoothFriendlyName = 0x17  # returns a 4-32 byte str ("BH " with network id appended)
    GetBluetoothUserConfig = 0xA3  # returns some flags
    GetBTLinkConfig = 0xA5  # returns 2 words for link timeout and lifesign period
    GetBioHarnessUserConfig = 0xA7  # returns all manner of settings
    GetBatteryStatus = 0xAC  # returns the voltage in mv as 2 bytes) and a percentage as a byte
    GetAccelerometerAxisMapping = 0xB5  # returns a complex spec
    GetAlgorithmConfig = 0xB7  # (payload is the algo type - 0..31)
    GetROGSettings = 0x9C   # returns a complex spec
    GetSubjectInfoSettings = 0xBF  # returns a complex spec
    GetRemoteMACAddressAndPIN = 0xD1  # returned payload is the MAC & PIN
    GetNetworkID = 0x11  # returned payload is a string (e.g., John Smith)
    GetRemoteDeviceDescription = 0xD4  # returns a device number and a description

    # benign configuration
    SetRTCDateTime = 0x07   # complex payload
    SetNetworkID = 0x10  # payload is a string, 2-29 chars (e.g., John Smith 5)

    # not-so-benign commands
    SetBluetoothUserConfig = 0xA2  # complex payload
    SetBTLinkConfig = 0xA4  # complex payload
    SetBioHarnessUserConfig = 0xA6  # complex payload
    RebootUnit = 0x1F  # payload must be the string ZReBoot (takes ca. 5.2 seconds)
    SetROGSettings = 0x9B   # complex payload - applicable to v1 of algo (ROG = red, orange, green)
    BluetoothPeripheralMessage = 0xB0  # complex stuff
    ResetConfiguration = 0xB3  # payload is 0 for factory defaults and 1 for all config except calib data
    SetAccelerometerAxisMapping = 0xB4  # complicated axis spec
    SetAlgorithmConfig = 0xB6  # various parameters
    SetBioHarnessUserConfigItem = 0xB9  # number of config item
    SetSubjectInfoSettings = 0xBE  # rather complex settings of per-subject limits etc
    SetRemoteMACAddressAndPIN = 0xD0  # can set mac and PIN

    # log access
    GetSupportedLogFormats = 0xD5   # pass the log file number
    ReadLoggingData = 0x01  # complex payload (byte range etc)
    SendLoggingData = 0xE2  # request logging data to be sent using a byte range
    DeleteLogfile = 0x02    # payload is the file number (byte)
    LiveLogAccessCommand = 0xE5  # configure OTA log transmit while still logging...


# shorthands
MC = MessageConstants
MI = MessageIDs

# message types that correspond to periodically send (streaming) data
periodic_messages = (
    MI.GeneralDataPacket, MI.BreathingWaveformPacket, MI.ECGWaveformPacket,
    MI.RtoRPacket, MI.AccelerometerPacket, MI.BluetoothDeviceDataPacket,
    MI.ExtendedDataPacket, MI.Accelerometer100MgPacket, MI.SummaryDataPacket,
    MI.EventPacket, MI.LoggingDataPacket, MI.LiveLogAccessDataPacket
)

# a table that maps transmit state change messages to data packet messages
transmit_state2data_packet = {
    MI.SetGeneralDataPacketTransmitState: MI.GeneralDataPacket,
    MI.SetBreathingWaveformPacketTransmitState: MI.BreathingWaveformPacket,
    MI.SetECGWaveformPacketTransmitState: MI.ECGWaveformPacket,
    MI.SetRtoRDataPacketTransmitState: MI.RtoRPacket,
    MI.SetAccelerometerPacketTransmitState: MI.AccelerometerPacket,
    MI.SetAccelerometer100mgPacketTransmitState: MI.Accelerometer100MgPacket,
    MI.SetExtendedDataPacketTransmitState: MI.ExtendedDataPacket,
    MI.SetSummaryDataPacketUpdateRate: MI.SummaryDataPacket
}


@functools.lru_cache(6)
def make_sequence_unpacker(vals_per_chunk, is_signed=False, bits_per_val=10):
    """Create a callable that can be used to unpack bits that are packed using
    the BHT bit-packing scheme into a seequence of ints.

    Args:
        vals_per_chunk: number of values in a data chunk
        is_signed: whether the values are stored as 2's complement signed integers
          (or the special value 'shift', which uses a shift by 1/2 the range)
        bits_per_val: the number of bits used to store each successive value

    Returns: a list of decoded numbers
    """
    bitfmt = f'<{"s" if is_signed == True else "u"}{bits_per_val}' * vals_per_chunk
    unpacker = bitstruct.compile(bitfmt)
    if is_signed == 'shift':
        return lambda seq: [v - 2**(bits_per_val - 1) if v != 0 else math.nan
                            for v in unpacker.unpack(bytes(reverse_bits8(seq)))]
    else:
        return lambda seq: unpacker.unpack(bytes(reverse_bits8(seq)))


def make_gps_pos_unpacker():
    """Create a callable that can be used to unpack a GPS position data structure
    from its custom bit-crushed representation used by BHT."""
    layout = {
        'lat_degrees': 'u7',
        'lat_minutes': 'u6',
        'lat_decimal_minutes': 'u14',
        'lat_dir': 's1',
        'long_degrees': 'u8',
        'long_minutes': 'u6',
        'long_decimal_minutes': 'u14',
        'long_dir': 's1',
        'qual_indication': 'u1',
        'altitude': 'u15',
        'horz_dilution_of_precision': 'u6'
    }
    fmt = '<' + ''.join(layout.values())
    names = list(layout.keys())
    unpacker = bitstruct.compile(fmt, names=names)
    return lambda seq: unpacker.unpack(bytes(reverse_bits8(seq)))


def make_accelerometry_unpacker():
    """Create a callable that can be used to unpack an accelerometry data
    structure from its custom bit-crushed representation used by BHT."""
    mapping = {
        'impulse_load': 'u20',  # Ns
        'walk_step_count': 'u18',
        'run_step_count': 'u18',
        'bound_count': 'u10',
        'jump_count': 'u10',
        'impact_count3g': 'u10',
        'impact_count7g': 'u10',
        'avg_rate_of_force_development': 'u12',  # * 0.01 N/s
        'avg_step_impulse': 'u10',  # * 0.01 Ns
        'avg_step_period': 'u10',   # * 0.001 s
        'last_jump_flight_time': 'u8',  # * 0.01 s
        'peak_accel_phi': 'u8',  # 0...180
        'peak_accel_theta': 's10',  # -179...180
    }
    fmt = '<' + ''.join(mapping.values())
    names = list(mapping.keys())
    unpacker = bitstruct.compile(fmt, names=names)
    return lambda seq: unpacker.unpack(bytes(reverse_bits8(seq)))


def parse_num(encoded, signed, *, inval=None, num_bytes=None):
    """Parse a sequence of bytes into a number

    Args:
        encoded: sequence of ints or bytes
        signed: whether this is a signed value or not
        inval: optionally a number that represents invalid data
        num_bytes: number of bytes to extract from encoded (if not provided,
          all is used)

    Returns:
        the value or NaN if matching the invalid code
    """
    # optionally deduce num_bytes
    if num_bytes is None:
        num_bytes = len(encoded)
        if num_bytes > 4:
            raise ValueError("num_bytes not specified")
    # extract from bytes
    num = 0
    for val in reversed(encoded[:num_bytes]):
        num = num*256 + int(val)
    # replace by nan if matching invalid
    if inval is not None and num == inval:
        num = math.nan
    # convert to two's complement
    if signed and encoded[num_bytes-1] > 127:
        num -= 2**(8*num_bytes)
    return num


@functools.lru_cache(maxsize=5)
def ymd2int_fast(year, month, day):
    """Convert year, month, and day into a unix timestamp."""
    dt = datetime.datetime(year=year, month=month, day=day)
    stamp = time.mktime(dt.timetuple())
    return stamp


def parse_timestamp(encoded):
    """Parse a bytes-encoded UNIX timestamp."""
    year = parse_num(encoded[0:2], False)
    month, day = encoded[2:4]
    msec = parse_num(encoded[4:8], False)
    stamp = ymd2int_fast(year, month, day) + msec*0.001
    return stamp


class Message:
    """A message that can be exchanged with the device (sent or received)."""
    def __init__(self, msgid, payload=(), fin=MC.ETX):
        self.msgid = msgid
        if not isinstance(payload, (list, tuple, bytes)):
            raise TypeError("payload must be a list, tuple, or bytes.")
        self.payload = payload
        self.fin = fin

    @classmethod
    def assert_length(cls, payload, expected_len, at_least=False):
        """Check if the length matches (or exceeds) the given expected length."""
        if (at_least and len(payload) < expected_len) or (not at_least and len(payload) != expected_len):
            raise AssertionError(f"{cls.__name__} requires at least {expected_len} "
                                 f"bytes of payload, but got {len(payload)}.")

    def payload_str(self, encoding='utf-8'):
        """Get the payload as a string."""
        return bytes(self.payload).decode(encoding)

    def ensure_fin_ok(self):
        """Checks if fin was OK, and otherwise raises an error"""
        if self.fin not in (MC.ACK, MC.ETX):
            raise RuntimeError(f"Error invoking {MI(self.msgid).name}: {self}")

    def as_dict(self):
        """Get the content as a dictionary."""
        return {k: v for k, v in self.__dict__.items()
                if not k.startswith('_') and k not in ('msgid', 'payload', 'fin')}

    def __str__(self):
        """Render a human-readable string."""
        content = ', '.join([f'{k}={v}' for k, v in self.__dict__.items() if not k.startswith('_')])
        return f'{self.__class__.__name__}({content})'


class StreamingMessage(Message):
    """Base class for messages that have a sequence num and time stamp."""
    def __init__(self, msgid, payload, fin=MC.ETX):
        self.assert_length(payload, 9, at_least=True)
        super().__init__(msgid, payload, fin)
        self.seq_no = payload[0]
        self.stamp = parse_timestamp(payload[1:])


class GeneralDataMessage(StreamingMessage):
    """A general data packet with various slow-changing state."""

    srate = 1.0

    def __init__(self, msgid, payload, fin=MC.ETX):
        self.assert_length(payload, 53)
        super().__init__(msgid, payload, fin)
        # in BPM; 0...240
        self.heart_rate = parse_num(payload[9:11], False, inval=0xFFFF)
        # per minute; 0..70, res 0.1
        self.respiration_rate = parse_num(payload[11:13], False, inval=0xFFFF) * 0.1
        # in deg C, 0...60, res 0.1 (but signed)
        self.skin_temperature = parse_num(payload[13:15], True, inval=0x8000) * 0.1
        # in degrees, -180 to 180, res 1
        self.posture = parse_num(payload[15:17], True, inval=0x8000)
        # in VMU, 0...16, res 0.01
        self.vmu_activity = parse_num(payload[17:19], False, inval=0xFFFF) * 0.01
        # in g 0..16, res 0.01
        self.peak_acceleration = parse_num(payload[19:21], False, inval=0xFFFF) * 0.01
        # in Volts 0...4.2, res 0.001
        self.battery_voltage = parse_num(payload[21:23], False, inval=0xFFFF) * 0.001
        # LSB 0...65535
        self.breathing_wave_amplitude = parse_num(payload[23:25], False, inval=0xFFFF)
        # volts, 0...0.05, res 0.000001
        self.ecg_amplitude = parse_num(payload[25:27], False, inval=0xFFFF) * 0.000001
        # volts, 0...0.05, res 0.000001 (noise floor?)
        self.ecg_noise = parse_num(payload[27:29], False, inval=0xFFFF) * 0.000001
        # in g, -16..16, res 0.01
        self.vertical_accel_min = parse_num(payload[29:31], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.vertical_accel_peak = parse_num(payload[31:33], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.lateral_accel_min = parse_num(payload[33:35], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.lateral_accel_peak = parse_num(payload[35:37], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.sagittal_accel_min = parse_num(payload[37:39], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.sagittal_accel_peak = parse_num(payload[39:41], True, inval=0x8000) * 0.01
        # zephyr system channel (undocumented)
        self.system_channel = parse_num(payload[41:43], False)
        # in nS (nano-Siemens)
        self.gsr = parse_num(payload[43:45], False, inval=0xFFFF)
        # denoted as unused
        self.unused1 = parse_num(payload[45:47], False, inval=0xFFFF)
        # denoted as unused
        self.unused2 = parse_num(payload[47:49], False, inval=0xFFFF)
        # undocumented
        self.rog = parse_num(payload[49:51], False, inval=0xFFFF)
        # undocumented
        self.alarm = parse_num(payload[49:51], False, inval=0xFFFF)
        # bit packed status
        status = parse_num(payload[51:53], False)
        # 1 if physiological monitor is worn
        self.physio_monitor_worn = status & (2**15) > 0
        # 1 if UI button is pressed
        self.ui_button_pressed = status & (2 ** 14) > 0
        # 1 if low ("HR coasting")
        self.heart_rate_is_low_quality = status & (2 ** 13) > 0
        # 1 if external sensors are connected
        self.external_sensors_connected = status & (2 ** 12) > 0
        # in percent
        self.battery_percent = status & 127


class SummaryDataMessage(StreamingMessage):
    """Common base class for the two versions of the summary data packet."""

    def _decode_status_info(self, status_info):
        """Parse status info word and write into state."""
        # 0...1 in steps of 0.25
        self.device_worn_confidence = 1 - (status_info & 3)/3
        # 1 if pressed
        self.button_pressed = (status_info & 2**2) > 0
        # 1 if not fitted
        self.not_fitted_to_garment = (status_info & 2**3) > 0
        # 1 if unreliable
        self.heart_rate_unreliable = (status_info & 2**4) > 0
        # 1 if unreliable
        self.respiration_rate_unreliable = (status_info & 2**5) > 0
        # 1 if unreliable
        self.skin_temperature_unreliable = (status_info & 2**6) > 0
        # 1 if unreliable
        self.posture_unreliable = (status_info & 2**7) > 0
        # 1 if unreliable
        self.activity_unreliable = (status_info & 2**8) > 0
        # 1 if unreliable
        self.hrv_unreliable = (status_info & 2**9) > 0
        # 1 if unreliable
        self.estimated_core_temp_unreliable = (status_info & 2**10) > 0
        # 1 if connected to USB power source
        self.usb_power_connected = (status_info & 2**11) > 0
        # 1 if subject is in resting state
        self.resting_state_detected = (status_info & 2**14) > 0
        # 1 if connected
        self.external_sensors_connected = (status_info & 2**15) > 0


class SummaryDataMessageV2(SummaryDataMessage):
    """A summary data packet with various slow-changing state."""

    srate = 1.0

    def __init__(self, msgid, payload, fin=MC.ETX):
        self.assert_length(payload, 71)
        super().__init__(msgid, payload, fin)
        ver = payload[9]
        assert ver == 2, """Version must be 2."""
        # in BPM; 0...240
        self.heart_rate = parse_num(payload[10:12], False, inval=0xFFFF)
        # per minute; 0..70, res 0.1
        self.respiration_rate = parse_num(payload[12:14], False, inval=0xFFFF) * 0.1
        # in deg C, 0...60, res 0.1 (but signed)
        self.skin_temperature = parse_num(payload[14:16], True, inval=0x8000) * 0.1
        # in degrees, -180 to 180, res 1
        self.posture = parse_num(payload[16:18], True, inval=0x8000)
        # 0...16, res 0.01
        self.activity = parse_num(payload[18:20], False, inval=0xFFFF) * 0.01
        # in g 0..16, res 0.01
        self.peak_acceleration = parse_num(payload[20:22], False, inval=0xFFFF) * 0.01
        # in Volts 0...4.2, res 0.001
        self.battery_voltage = parse_num(payload[22:24], False, inval=0xFFFF) * 0.001
        # in %, 0...100
        self.battery_percent = parse_num(payload[24:25], False, inval=0xFF)
        # LSB 0...65535
        self.breathing_wave_amplitude = parse_num(payload[25:27], False, inval=0xFFFF)
        # LSB 0...65535
        self.breathing_wave_noise = parse_num(payload[27:29], False, inval=0xFFFF)
        # in %, 0...100
        self.breathing_rate_confidence = parse_num(payload[29:30], False, inval=0xFF)
        # volts, 0...0.05, res 0.000001
        self.ecg_amplitude = parse_num(payload[30:32], False, inval=0xFFFF) * 0.000001
        # volts, 0...0.05, res 0.000001 (noise floor?)
        self.ecg_noise = parse_num(payload[32:34], False, inval=0xFFFF) * 0.000001
        # in %, 0...100
        self.heart_rate_confidence = parse_num(payload[34:35], False, inval=0xFF)
        # 0...65534
        self.heart_rate_variability = parse_num(payload[35:37], False, inval=0xFFFF)
        # in %, 0...100
        self.system_confidence = parse_num(payload[37:38], False, inval=0xFF)
        # in nS (nano-Siemens)
        self.gsr = parse_num(payload[38:40], False, inval=0xFFFF)
        # ??
        self.rog = parse_num(payload[40:42], False, inval=0)
        # in g, -16..16, res 0.01
        self.vertical_accel_min = parse_num(payload[42:44], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.vertical_accel_peak = parse_num(payload[44:46], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.lateral_accel_min = parse_num(payload[46:48], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.lateral_accel_peak = parse_num(payload[48:50], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.sagittal_accel_min = parse_num(payload[50:52], True, inval=0x8000) * 0.01
        # in g, -16..16, res 0.01
        self.sagittal_accel_peak = parse_num(payload[52:54], True, inval=0x8000) * 0.01
        # in deg C, 0...100, res 0.1
        self.device_internal_temp = parse_num(payload[54:56], True, inval=0x8000) * 0.1
        # ??
        status_info = parse_num(payload[56:58], False, inval=0)
        self._decode_status_info(status_info)
        # 0...254 (unitless)
        self.link_quality = parse_num(payload[58:59], False, inval=0xFF)
        # -127...127
        self.rssi = parse_num(payload[59:60], False, inval=0x80)
        # -30..20
        self.tx_power = parse_num(payload[60:61], False, inval=0x80)
        # in dec C, 33...41, res 0.1
        self.estimated_core_temperature = parse_num(payload[61:63], False, inval=0xFFFF) * 0.1
        # 0...645534
        self.aux_adc_chan1 = parse_num(payload[63:65], False, inval=0xFFFF)
        # 0...645534
        self.aux_adc_chan2 = parse_num(payload[65:67], False, inval=0xFFFF)
        # 0...645534
        self.aux_adc_chan3 = parse_num(payload[67:69], False, inval=0xFFFF)
        # custom format
        ext_status_info = parse_num(payload[69:71], False, inval=0xFFFF)
        flags_valid = 0 if (ext_status_info & 2**15) > 0 else math.nan
        # 1 if low
        self.resp_rate_low = (ext_status_info & 2 ** 0) > 0 + flags_valid
        # 1 if high
        self.resp_rate_high = (ext_status_info & 2 ** 1) > 0 + flags_valid
        # 1 if low
        self.br_amplitude_low = (ext_status_info & 2 ** 2) > 0 + flags_valid
        # 1 if high
        self.br_amplitude_high = (ext_status_info & 2 ** 3) > 0 + flags_valid
        # 1 if high
        self.br_amplitude_variance_high = (ext_status_info & 2 ** 4) > 0 + flags_valid
        # 0 running, 1 failed, 2 passed, 3 interrupted
        self.br_signal_eval_state = (ext_status_info >> 5) & 3 + flags_valid


class SummaryDataMessageV3(SummaryDataMessage):
    """A general data packet with various slow-changing state."""

    srate = 1.0

    # unpacker function for GPS position data
    gps_pos_unpacker = make_gps_pos_unpacker()
    # unpacker for accelerometry data
    accelerometry_unpacker = make_accelerometry_unpacker()

    # noinspection PyUnresolvedReferences
    def __init__(self, msgid, payload, fin=MC.ETX):
        self.assert_length(payload, 71)
        super().__init__(msgid, payload, fin)
        ver = payload[9]
        assert ver == 3, """Version must be 3."""
        # in BPM; 0...240
        self.heart_rate = parse_num(payload[10:12], False, inval=0xFFFF)
        # per minute; 0..70, res 0.1
        self.respiration_rate = parse_num(payload[12:14], False, inval=0xFFFF) * 0.1
        # in degrees, -180 to 180, res 1
        self.posture = parse_num(payload[14:16], True, inval=0x8000)
        # 0...16, res 0.01
        self.activity = parse_num(payload[16:18], False, inval=0xFFFF) * 0.01
        # in g 0..16, res 0.01
        self.peak_acceleration = parse_num(payload[18:20], False, inval=0xFFFF) * 0.01
        # in %, 0...100
        self.battery_percent = parse_num(payload[20:21], False)
        # LSB 0...65535
        self.breathing_wave_amplitude = parse_num(payload[21:23], False, inval=0xFFFF)
        # volts, 0...0.05, res 0.000001
        self.ecg_amplitude = parse_num(payload[23:25], False, inval=0xFFFF) * 0.000001
        # volts, 0...0.05, res 0.000001 (noise floor?)
        self.ecg_noise = parse_num(payload[25:27], False, inval=0xFFFF) * 0.000001
        # in %, 0...100
        self.heart_rate_confidence = parse_num(payload[27:28], False)
        # 0...65534
        self.heart_rate_variability = parse_num(payload[28:30], False, inval=0xFFFF)
        # custom
        self.rog = parse_num(payload[30:32], False, inval=0)
        # custom structure
        status_info = parse_num(payload[32:34], False, inval=0)
        self._decode_status_info(status_info)
        # 0...254 (unitless)
        self.link_quality = parse_num(payload[34:35], False, inval=0xFF)
        # -127...127
        self.rssi = parse_num(payload[35:36], False, inval=0x80)
        # -30..20
        self.tx_power = parse_num(payload[36:37], False, inval=0x80)
        # in dec C, 33...41, res 0.1 (only LSB given)
        self.estimated_core_temperature = parse_num([payload[37], 256], False, inval=0xFFFF) * 0.1
        # GPS position data
        self.__dict__.update(SummaryDataMessageV3.gps_pos_unpacker(payload[38:48]))
        # speed
        self.gps_speed = parse_num(payload[48:50], False) & 0x3FFF
        # accelerometry
        self.__dict__.update(SummaryDataMessageV3.accelerometry_unpacker(payload[51:71]))
        self.avg_rate_of_force_development *= 0.01  # N/s
        self.avg_step_impulse *= 0.01  # Ns
        self.avg_step_period *= 0.001  # s
        self.last_jump_flight_time *= 0.01  # s


class WaveformMessage(StreamingMessage):
    """A message that holds a waveform."""

    def __init__(self, msgid, payload, fin, bytes_per_chunk, signed):
        super().__init__(msgid, payload, fin)
        # extract waveform, skipping the seq no & timestamp
        waveform = []
        values_per_chunk = bytes_per_chunk*4//5
        unpacker = make_sequence_unpacker(values_per_chunk, is_signed=signed)
        for ofs in range(9, len(payload), bytes_per_chunk):
            packed = payload[ofs:ofs+bytes_per_chunk]
            # pad to full length so we don't get decode errors
            if len(packed) < 5:
                # noinspection PyTypeChecker
                packed = packed + [0] * (5 - len(packed))
            vals = unpacker(packed)
            waveform.extend(vals)
        self.waveform = waveform


class ECGWaveformMessage(WaveformMessage):
    """ECG waveform message."""
    srate = 250

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 88)
        super().__init__(msgid, payload, fin, bytes_per_chunk=5, signed='shift')


class BreathingWaveformMessage(WaveformMessage):
    """Breathing (respiration) waveform message."""
    srate = 1000.0/56

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 32)
        super().__init__(msgid, payload, fin, bytes_per_chunk=5, signed='shift')


class AccelerometerWaveformMessage(WaveformMessage):
    """Accelerometer waveform message."""
    srate = 50

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 84)
        super().__init__(msgid, payload, fin, bytes_per_chunk=15, signed=True)
        self.accel_x = self.waveform[::3]
        self.accel_y = self.waveform[1::3]
        self.accel_z = self.waveform[2::3]
        del self.waveform


class Accelerometer100MgWaveformMessage(WaveformMessage):
    """Accelerometer waveform message in units of 0.1g."""
    srate = 50

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 84)
        super().__init__(msgid, payload, fin, bytes_per_chunk=15, signed=True)
        waveform = [w*0.1 for w in self.waveform]
        # in units of g, res 0.1
        self.accel_x = waveform[::3]
        self.accel_y = waveform[1::3]
        self.accel_z = waveform[2::3]
        del self.waveform


class RtoRMessage(StreamingMessage):
    srate = 1000.0 / 56

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 45)
        super().__init__(msgid, payload, fin)
        # 16-bit values
        self.waveform = [parse_num(payload[ofs:ofs+2], False) for ofs in range(9, len(payload), 2)]


class EventMessage(StreamingMessage):
    """A message that holds event codes."""
    def __init__(self, msgid, payload, fin):
        super().__init__(msgid, payload, fin)
        self.event_code = parse_num(payload[9:11], False)
        self.event_data = bytes(payload[11:])


def decode_message(msgid, payload=(), fin=MC.ETX):
    """Decode raw message data into a message object of appropriate type."""
    msgid = MI(msgid)
    if msgid == MI.ECGWaveformPacket:
        return ECGWaveformMessage(msgid, payload, fin)
    elif msgid == MI.Accelerometer100MgPacket:
        return Accelerometer100MgWaveformMessage(msgid, payload, fin)
    elif msgid == MI.AccelerometerPacket:
        return AccelerometerWaveformMessage(msgid, payload, fin)
    elif msgid == MI.BreathingWaveformPacket:
        return BreathingWaveformMessage(msgid, payload, fin)
    elif msgid == MI.EventPacket:
        return EventMessage(msgid, payload, fin)
    elif msgid == MI.GeneralDataPacket:
        return GeneralDataMessage(msgid, payload, fin)
    elif msgid == MI.SummaryDataPacket:
        ver = payload[9]
        if ver == 3:
            return SummaryDataMessageV3(msgid, payload, fin)
        elif ver == 2:
            return SummaryDataMessageV2(msgid, payload, fin)
        else:
            logger.warning("Unsupported summary data packet version.")
    elif msgid == MI.RtoRPacket:
        return RtoRMessage(msgid, payload, fin)
    elif msgid in MI:
        return Message(msgid, payload, fin)
    else:
        raise ValueError("Invalid message id.")


def encode_message(msg):
    """Encode a given message into a bytes object for transmission."""
    msg = bytes([MC.STX, msg.msgid,
                 len(msg.payload), *msg.payload, crc8(msg.payload),
                 msg.fin])
    return msg


def decode_bytestream(stream):
    """Generator function that consumes bytes from a stream and yields Message
    objects."""
    valid_fins = (MC.ETX, MC.ACK, MC.NAK)
    # for each message...
    while True:
        good = True

        # scan for the start of the next message
        while next(stream) != MC.STX:
            pass

        # read and verify message ID
        msgid = next(stream)
        known = msgid in MI.__members__.values()
        if not known:
            logger.info("Unknown message ID encountered (%02x)" % msgid)
            good = False

        # read payload length
        payload_len = next(stream)
        if payload_len > 128:
            logger.error(f"Invalid payload length > 128 encountered ({payload_len})")
            # scan to the end of the message
            # (we do this so that we don't lose unnecessary data by skipping
            # a bogus amount of data)
            logger.info("Skipping rest of message.")
            while next(stream) not in valid_fins:
                pass
            continue

        # read payload
        payload = [next(stream) for _ in range(payload_len)]

        # read CRC code
        crc = next(stream)

        # check payload CRC
        valid = crc == crc8(bytes(payload))
        if not valid:
            logger.error("Payload CRC does not match. Discarding message.")
            good = False

        # check for ETX, ACK, or NAK
        fin = next(stream)
        if fin not in valid_fins:
            logger.error(f"Message was not termiated by a valid byte (got: "
                         f"{fin}, expected one of {valid_fins}).")
            good = False

        # parse and emit message
        if good:
            try:
                msg = decode_message(msgid, payload, fin)
                if msg:
                    yield msg
            except Exception as e:
                logger.exception(f"Message with id {msgid} was corrupted: {e}")


def _debug_unpacker(unpacker, datadict):
    """Helper function to debug the bit patterns read by an unpacker.
    Use an unpacker (e.g., accelerometry), and stick in a data dict, then compare
    the resulting bit pattern vs the table in the spec. Use values such as 0xFFFF
    or 0xFFFF-2 to see where the different bits of a value land.
    """
    # use an unpacker put your bits here
    packed = reverse_bits8(unpacker.pack(datadict))
    # print the bytes
    print(' '.join([f'{k:02d} {v:08b}\n' for k, v in enumerate(packed)]))
