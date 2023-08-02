"""Protocol definitions for Zephyr BioHarness and byte stream encoding/decoding
logic. This implements only a fraction of the device functionality as needed for
data streaming."""

import enum
import math
import functools
import logging
import cbitstruct as bitstruct

from .utilities import crc8, reverse_bits8, date2stamp_cached

__all__ = ['MessageConstants', 'Message', 'MC', 'MI', 'encode_message',
           'decode_bytestream', 'periodic_messages', 'transmit_state2data_packet',
           'StreamingMessage', 'GeneralDataMessage', 'SummaryDataMessageV2',
           'SummaryDataMessageV3', 'WaveformMessage', 'ECGWaveformMessage',
           'BreathingWaveformMessage', 'Accelerometer100MgWaveformMessage',
           'AccelerometerWaveformMessage', 'RtoRMessage', 'EventMessage',
           'get_unit']

logger = logging.getLogger(__name__)


class MessageConstants(enum.IntEnum):
    """Generic constants used in BHT framing protocol."""

    # start of text (first byte in a msg)
    STX = 0x02
    # end of text (last byte in a msg)
    ETX = 0x03
    # acknowledged
    ACK = 0x06
    # not acknowledged
    NAK = 0x15


class MessageIDs(enum.IntEnum):
    """Various message IDs needed to implement functionality of this interface."""

    # --- periodic data packets sent by the device (once enabled) ---

    GeneralDataPacket = 0x20
    BreathingWaveformPacket = 0x21
    ECGWaveformPacket = 0x22
    RtoRPacket = 0x24
    AccelerometerPacket = 0x25
    BluetoothDeviceDataPacket = 0x27
    ExtendedDataPacket = 0x28
    Accelerometer100MgPacket = 0x2A
    SummaryDataPacket = 0x2B
    EventPacket = 0x2C
    LoggingDataPacket = 0x3F
    LiveLogAccessDataPacket = 0x60

    # keepalive message
    Lifesign = 0x23

    # --- commands ---

    # toggling various data streams
    SetGeneralDataPacketTransmitState = 0x14
    SetBreathingWaveformPacketTransmitState = 0x15
    SetECGWaveformPacketTransmitState = 0x16
    SetRtoRDataPacketTransmitState = 0x19
    SetAccelerometerPacketTransmitState = 0x1E
    SetAccelerometer100mgPacketTransmitState = 0xBC
    SetExtendedDataPacketTransmitState = 0xB8
    SetSummaryDataPacketUpdateRate = 0xBD

    # queries
    GetRTCDateTime = 0x08
    GetBootSoftwareVersion = 0x09
    GetApplicationSoftwareVersion = 0x0A
    GetSerialNumber = 0x0B
    GetHardwarePartNumber = 0x0C
    GetBootloaderPartNumber = 0x0D
    GetApplicationPartNumber = 0x0E
    GetUnitMACAddress = 0x12
    GetUnitBluetoothFriendlyName = 0x17
    GetBluetoothUserConfig = 0xA3
    GetBTLinkConfig = 0xA5
    GetBioHarnessUserConfig = 0xA7
    GetBatteryStatus = 0xAC
    GetAccelerometerAxisMapping = 0xB5
    GetAlgorithmConfig = 0xB7
    GetROGSettings = 0x9C
    GetSubjectInfoSettings = 0xBF
    GetRemoteMACAddressAndPIN = 0xD1
    GetNetworkID = 0x11
    GetRemoteDeviceDescription = 0xD4

    # (other device commands not implemented here)


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

# unit map needed for LSL metadata
parameter_units = {
    'activity': 'g',
    'activity_unreliable': 'binary',
    'avg_rate_of_force_development': 'N/s',
    'avg_step_impulse': 'Ns',
    'avg_step_period': 'seconds',
    'battery_percent': 'percent',
    'battery_voltage': 'Volts',
    'bound_count': 'count',
    'br_amplitude_high': 'binary',
    'br_amplitude_low': 'binary',
    'br_amplitude_variance_high': 'binary',
    'breathing_rate_confidence': 'percent',
    'breathing_wave_amplitude': 'unnormalized',
    'breathing_wave_noise': 'unnormalized',
    'button_pressed': 'binary',
    'device_internal_temp': 'degrees C',
    'device_worn_confidence': 'normalized',
    'ecg_amplitude': 'Volts',
    'ecg_noise': 'Volts',
    'estimated_core_temp_unreliable': 'binary',
    'estimated_core_temperature': 'degrees C',
    'external_sensors_connected': 'binary',
    'gsr': 'nanosiemens',
    'heart_rate': 'BPM',
    'heart_rate_confidence': 'percent',
    'heart_rate_is_low_quality': 'binary',
    'heart_rate_unreliable': 'binary',
    'heart_rate_variability': 'ms',
    'hrv_unreliable': 'binary',
    'impact_count3g': 'count',
    'impact_count7g': 'count',
    'impulse_load': 'Ns',
    'jump_count': 'count',
    'last_jump_flight_time': 'seconds',
    'lat_degrees': 'degrees',
    'lat_minutes': 'minutes',
    'lateral_accel_min': 'g',
    'lateral_accel_peak': 'g',
    'link_quality': 'percent',
    'long_degrees': 'degrees',
    'long_minutes': 'minutes',
    'not_fitted_to_garment': 'binary',
    'peak_accel_phi': 'degrees',
    'peak_accel_theta': 'degrees',
    'peak_acceleration': 'g',
    'physio_monitor_worn': 'binary',
    'posture': 'degrees',
    'posture_unreliable': 'binary',
    'qual_indication': 'binary',
    'resp_rate_high': 'binary',
    'resp_rate_low': 'binary',
    'respiration_rate': 'BPM',
    'respiration_rate_unreliable': 'binary',
    'resting_state_detected': 'binary',
    'rssi': 'dB',
    'run_step_count': 'count',
    'sagittal_accel_min': 'g',
    'sagittal_accel_peak': 'g',
    'skin_temperature': 'degrees C',
    'skin_temperature_unreliable': 'binary',
    'system_confidence': 'percent',
    'tx_power': 'dBm',
    'ui_button_pressed': 'binary',
    'usb_power_connected': 'binary',
    'vertical_accel_min': 'g',
    'vertical_accel_peak': 'g',
    'walk_step_count': 'count'
}


def get_unit(param):
    """Get the unit for a named parameter."""
    return parameter_units.get(param, None)


@functools.lru_cache(10)
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
    from its compressed representation."""
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
    # bits for each byte need to be reversed since the bit-packing scheme shifts
    # in remaining bits from the previous value starting from the least-significant
    # bit
    return lambda seq: unpacker.unpack(bytes(reverse_bits8(seq)))


def make_accelerometry_unpacker():
    """Create a callable that can be used to unpack an accelerometry data
    structure from its compressed representation."""
    mapping = {
        'impulse_load': 'u20',  # Ns
        'walk_step_count': 'u18',
        'run_step_count': 'u18',
        'bound_count': 'u10',
        'jump_count': 'u10',
        'impact_count3g': 'u10',
        'impact_count7g': 'u10',
        'avg_rate_of_force_development': 'u12',
        'avg_step_impulse': 'u10',
        'avg_step_period': 'u10',
        'last_jump_flight_time': 'u8',
        'peak_accel_phi': 'u8',  # 0...180
        'peak_accel_theta': 's10',  # -179...180
    }
    fmt = '<' + ''.join(mapping.values())
    names = list(mapping.keys())
    unpacker = bitstruct.compile(fmt, names=names)
    # decode with bit reversal
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


def parse_timestamp(encoded):
    """Parse a bytes-encoded UNIX timestamp."""
    year = parse_num(encoded[0:2], False)
    month, day = encoded[2:4]
    msec = parse_num(encoded[4:8], False)
    stamp = date2stamp_cached(year, month, day) + msec * 0.001
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
        self.heart_rate = parse_num(payload[9:11], False, inval=0xFFFF)
        self.respiration_rate = parse_num(payload[11:13], False, inval=0xFFFF) * 0.1
        self.skin_temperature = parse_num(payload[13:15], True, inval=0x8000) * 0.1
        self.posture = parse_num(payload[15:17], True, inval=0x8000)
        self.vmu_activity = parse_num(payload[17:19], False, inval=0xFFFF) * 0.01
        self.peak_acceleration = parse_num(payload[19:21], False, inval=0xFFFF) * 0.01
        self.battery_voltage = parse_num(payload[21:23], False, inval=0xFFFF) * 0.001
        self.breathing_wave_amplitude = parse_num(payload[23:25], False, inval=0xFFFF)
        self.ecg_amplitude = parse_num(payload[25:27], False, inval=0xFFFF) * 0.000001
        self.ecg_noise = parse_num(payload[27:29], False, inval=0xFFFF) * 0.000001
        self.vertical_accel_min = parse_num(payload[29:31], True, inval=0x8000) * 0.01
        self.vertical_accel_peak = parse_num(payload[31:33], True, inval=0x8000) * 0.01
        self.lateral_accel_min = parse_num(payload[33:35], True, inval=0x8000) * 0.01
        self.lateral_accel_peak = parse_num(payload[35:37], True, inval=0x8000) * 0.01
        self.sagittal_accel_min = parse_num(payload[37:39], True, inval=0x8000) * 0.01
        self.sagittal_accel_peak = parse_num(payload[39:41], True, inval=0x8000) * 0.01
        self.system_channel = parse_num(payload[41:43], False)
        self.gsr = parse_num(payload[43:45], False, inval=0xFFFF)
        self.unused1 = parse_num(payload[45:47], False, inval=0xFFFF)
        self.unused2 = parse_num(payload[47:49], False, inval=0xFFFF)
        self.rog = parse_num(payload[49:51], False, inval=0xFFFF)
        self.alarm = parse_num(payload[49:51], False, inval=0xFFFF)
        status = parse_num(payload[51:53], False)
        self.physio_monitor_worn = status & (2**15) > 0
        self.ui_button_pressed = status & (2 ** 14) > 0
        self.heart_rate_is_low_quality = status & (2 ** 13) > 0
        self.external_sensors_connected = status & (2 ** 12) > 0
        self.battery_percent = status & 127


class SummaryDataMessage(StreamingMessage):
    """Common base class for the two versions of the summary data packet."""

    def _decode_status_info(self, status_info):
        """Parse status info word and write into state."""
        self.device_worn_confidence = 1 - (status_info & 3)/3
        self.button_pressed = (status_info & 2**2) > 0
        self.not_fitted_to_garment = (status_info & 2**3) > 0
        self.heart_rate_unreliable = (status_info & 2**4) > 0
        self.respiration_rate_unreliable = (status_info & 2**5) > 0
        self.skin_temperature_unreliable = (status_info & 2**6) > 0
        self.posture_unreliable = (status_info & 2**7) > 0
        self.activity_unreliable = (status_info & 2**8) > 0
        self.hrv_unreliable = (status_info & 2**9) > 0
        self.estimated_core_temp_unreliable = (status_info & 2**10) > 0
        self.usb_power_connected = (status_info & 2**11) > 0
        self.resting_state_detected = (status_info & 2**14) > 0
        self.external_sensors_connected = (status_info & 2**15) > 0


class SummaryDataMessageV2(SummaryDataMessage):
    """A summary data packet with various slow-changing state."""

    srate = 1.0

    def __init__(self, msgid, payload, fin=MC.ETX):
        self.assert_length(payload, 71)
        super().__init__(msgid, payload, fin)
        ver = payload[9]
        assert ver == 2, """Version must be 2."""
        self.heart_rate = parse_num(payload[10:12], False, inval=0xFFFF)
        self.respiration_rate = parse_num(payload[12:14], False, inval=0xFFFF) * 0.1
        self.skin_temperature = parse_num(payload[14:16], True, inval=0x8000) * 0.1
        self.posture = parse_num(payload[16:18], True, inval=0x8000)
        self.activity = parse_num(payload[18:20], False, inval=0xFFFF) * 0.01
        self.peak_acceleration = parse_num(payload[20:22], False, inval=0xFFFF) * 0.01
        self.battery_voltage = parse_num(payload[22:24], False, inval=0xFFFF) * 0.001
        self.battery_percent = parse_num(payload[24:25], False, inval=0xFF)
        self.breathing_wave_amplitude = parse_num(payload[25:27], False, inval=0xFFFF)
        self.breathing_wave_noise = parse_num(payload[27:29], False, inval=0xFFFF)
        self.breathing_rate_confidence = parse_num(payload[29:30], False, inval=0xFF)
        self.ecg_amplitude = parse_num(payload[30:32], False, inval=0xFFFF) * 0.000001
        self.ecg_noise = parse_num(payload[32:34], False, inval=0xFFFF) * 0.000001
        self.heart_rate_confidence = parse_num(payload[34:35], False, inval=0xFF)
        self.heart_rate_variability = parse_num(payload[35:37], False, inval=0xFFFF)
        self.system_confidence = parse_num(payload[37:38], False, inval=0xFF)
        self.gsr = parse_num(payload[38:40], False, inval=0xFFFF)
        self.rog = parse_num(payload[40:42], False, inval=0)
        self.vertical_accel_min = parse_num(payload[42:44], True, inval=0x8000) * 0.01
        self.vertical_accel_peak = parse_num(payload[44:46], True, inval=0x8000) * 0.01
        self.lateral_accel_min = parse_num(payload[46:48], True, inval=0x8000) * 0.01
        self.lateral_accel_peak = parse_num(payload[48:50], True, inval=0x8000) * 0.01
        self.sagittal_accel_min = parse_num(payload[50:52], True, inval=0x8000) * 0.01
        self.sagittal_accel_peak = parse_num(payload[52:54], True, inval=0x8000) * 0.01
        self.device_internal_temp = parse_num(payload[54:56], True, inval=0x8000) * 0.1
        status_info = parse_num(payload[56:58], False, inval=0)
        self._decode_status_info(status_info)
        self.link_quality = parse_num(payload[58:59], False, inval=0xFF)*100/254
        self.rssi = parse_num(payload[59:60], False, inval=0x80)
        self.tx_power = parse_num(payload[60:61], False, inval=0x80)
        self.estimated_core_temperature = parse_num(payload[61:63], False, inval=0xFFFF) * 0.1
        self.aux_adc_chan1 = parse_num(payload[63:65], False, inval=0xFFFF)
        self.aux_adc_chan2 = parse_num(payload[65:67], False, inval=0xFFFF)
        self.aux_adc_chan3 = parse_num(payload[67:69], False, inval=0xFFFF)
        ext_status_info = parse_num(payload[69:71], False, inval=0xFFFF)
        flags_valid = 0 if (ext_status_info & 2**15) > 0 else math.nan
        self.resp_rate_low = (ext_status_info & 2 ** 0) > 0 + flags_valid
        self.resp_rate_high = (ext_status_info & 2 ** 1) > 0 + flags_valid
        self.br_amplitude_low = (ext_status_info & 2 ** 2) > 0 + flags_valid
        self.br_amplitude_high = (ext_status_info & 2 ** 3) > 0 + flags_valid
        self.br_amplitude_variance_high = (ext_status_info & 2 ** 4) > 0 + flags_valid
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
        self.heart_rate = parse_num(payload[10:12], False, inval=0xFFFF)
        self.respiration_rate = parse_num(payload[12:14], False, inval=0xFFFF) * 0.1
        self.posture = parse_num(payload[14:16], True, inval=0x8000)
        self.activity = parse_num(payload[16:18], False, inval=0xFFFF) * 0.01
        self.peak_acceleration = parse_num(payload[18:20], False, inval=0xFFFF) * 0.01
        self.battery_percent = parse_num(payload[20:21], False)
        self.breathing_wave_amplitude = parse_num(payload[21:23], False, inval=0xFFFF)
        self.ecg_amplitude = parse_num(payload[23:25], False, inval=0xFFFF) * 0.000001
        self.ecg_noise = parse_num(payload[25:27], False, inval=0xFFFF) * 0.000001
        self.heart_rate_confidence = parse_num(payload[27:28], False)
        self.heart_rate_variability = parse_num(payload[28:30], False, inval=0xFFFF)
        self.rog = parse_num(payload[30:32], False, inval=0)
        status_info = parse_num(payload[32:34], False, inval=0)
        self._decode_status_info(status_info)
        self.link_quality = parse_num(payload[34:35], False, inval=0xFF)*100/254
        self.rssi = parse_num(payload[35:36], False, inval=0x80)
        self.tx_power = parse_num(payload[36:37], False, inval=0x80)
        self.estimated_core_temperature = parse_num(payload[37:39], False, inval=0xFFFF) * 0.1
        self.__dict__.update(SummaryDataMessageV3.gps_pos_unpacker(payload[39:49]))
        self.gps_speed = parse_num(payload[49:51], False) & 0x3FFF
        self.__dict__.update(SummaryDataMessageV3.accelerometry_unpacker(payload[51:71]))
        self.avg_rate_of_force_development *= 0.01
        self.avg_step_impulse *= 0.01
        self.avg_step_period *= 0.001
        self.last_jump_flight_time *= 0.01


class WaveformMessage(StreamingMessage):
    """A message that holds a waveform."""

    def __init__(self, msgid, payload, fin, bytes_per_chunk, vals_per_packet, signed):
        """
        Create a new WaveformMessage.

        Args:
            msgid: the message id
            payload: payload bytes
            fin: the finalizer of the message
            bytes_per_chunk: number of bytes per repeating "chunk" in the payload
              (each chunk has the same bit-packing pattern)
            vals_per_packet: total values encoded in packet (needed to identify
              truncated chunks at end of payload)
            signed: whether the values are 2's complement signed (True) or
              unsigned (False), or unsigned but range-shifted ('shift')

        """
        super().__init__(msgid, payload, fin)
        # extract waveform, skipping the seq no & timestamp
        waveform = []
        vals_per_chunk = bytes_per_chunk*4//5  # here: 10-bit values
        unpacker = make_sequence_unpacker(vals_per_chunk, is_signed=signed)
        for ofs in range(9, len(payload), bytes_per_chunk):
            packed = payload[ofs:ofs+bytes_per_chunk]
            # at the end we may have a truncated packet, need to decode fewer
            # values
            if vals_per_packet < vals_per_chunk:
                unpacker = make_sequence_unpacker(vals_per_packet, is_signed=signed)
            vals = unpacker(packed)
            vals_per_packet -= vals_per_chunk
            waveform.extend(vals)
        self.waveform = waveform


class ECGWaveformMessage(WaveformMessage):
    """ECG waveform message."""
    srate = 250

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 88)
        super().__init__(msgid, payload, fin, bytes_per_chunk=5,
                         vals_per_packet=63, signed='shift')
        self.waveform = [w*0.025 for w in self.waveform]  # to mV


class BreathingWaveformMessage(WaveformMessage):
    """Breathing (respiration) waveform message."""
    srate = 1000.0/56

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 32)
        super().__init__(msgid, payload, fin, bytes_per_chunk=5,
                         vals_per_packet=18, signed='shift')


class AccelerometerWaveformMessage(WaveformMessage):
    """Accelerometer waveform message."""
    srate = 50

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 84)
        super().__init__(msgid, payload, fin, bytes_per_chunk=15,
                         vals_per_packet=3*20, signed='shift')
        self.accel_x = self.waveform[::3]
        self.accel_y = self.waveform[1::3]
        self.accel_z = self.waveform[2::3]
        del self.waveform


class Accelerometer100MgWaveformMessage(WaveformMessage):
    """Accelerometer waveform message in units of 0.1g."""
    srate = 50

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 84)
        super().__init__(msgid, payload, fin, bytes_per_chunk=15,
                         vals_per_packet=3*20, signed=True)
        waveform = [w*0.1 for w in self.waveform]  # to g
        self.accel_x = waveform[::3]
        self.accel_y = waveform[1::3]
        self.accel_z = waveform[2::3]
        del self.waveform


class RtoRMessage(StreamingMessage):
    srate = 1000.0 / 56

    def __init__(self, msgid, payload, fin):
        self.assert_length(payload, 45)
        super().__init__(msgid, payload, fin)
        # 16-bit values of alternating sign
        self.waveform = [parse_num(payload[ofs:ofs+2], True)
                         for ofs in range(9, len(payload), 2)]


class EventMessage(StreamingMessage):

    # map of known event codes
    event_map = {
        0x0040: 'button press',
        0x0041: 'emergency button press',
        0x0080: 'battery level low',
        0x00C0: 'self test result',
        0x1000: 'ROG change',
        0x1040: 'worn status change',
        0x1080: 'HR reliability change',
        0x10C0: 'fall detected',
        0x1100: 'jump detected',
        0x1140: 'dash detected'
    }

    """A message that holds event codes."""
    def __init__(self, msgid, payload, fin):
        super().__init__(msgid, payload, fin)
        self.event_code = parse_num(payload[9:11], False)
        self.event_string = EventMessage.event_map.get(self.event_code, f'unknown:{self.event_code}')
        # event-specific data (we just store the bytes; see vendor SDK manual
        # for the interpretation)
        self.event_data = payload[11:]


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
    """Decode a provided bytestream into Message objects; implemented as a
    Generator that yields messages when iterated over."""
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
            logger.info(f"Unknown message ID encountered ({hex(msgid)})")
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
