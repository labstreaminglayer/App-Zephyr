"""Small utilities needed to implement the BHT protocol."""

import time
import datetime
import functools

__all__ = ['crc8', 'reverse_bits8', 'date2stamp_cached', 'debug_unpacker']


def crc8_slow(payload):
    """Calculate CRC8 for the given payload sequence (slow method).  This is
    not a standard CRC8 but BHT-specific."""
    crc = 0
    for b in payload:
        crc ^= int(b)
        for bit in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8C
            else:
                crc = (crc >> 1)
    return crc


def reverse_bits8_slow(n):
    """Reverse the bits in a byte."""
    return int('{:08b}'.format(n)[::-1], 2)


# pre-calculated lookup table for the fast CRC8 function below
CRC_LUT = [crc8_slow([b]) for b in range(256)]

# pre-calculated lookup table to reverse the bits of a byte
REVERSE_BITS_LUT = [reverse_bits8_slow(b) for b in range(256)]


def crc8(payload):
    """Calc a CRC8 of the given payload sequence (using a lookup table, i.e.,
    fast). This is not a standard CRC8 but BHT-specific."""
    accum = 0
    for b in payload:
        accum = CRC_LUT[accum ^ b]
    return accum


def reverse_bits8(seq):
    """Reverse bits in a sequence of bytes using a lookup table."""
    return [REVERSE_BITS_LUT[b] for b in seq]



@functools.lru_cache(maxsize=5)
def date2stamp_cached(year, month, day):
    """Convert year, month, and day into a unix timestamp."""
    dt = datetime.datetime(year=year, month=month, day=day)
    stamp = time.mktime(dt.timetuple())
    return stamp


def debug_unpacker(unpacker, datadict):
    """Helper function to debug the bit patterns read by a cbitstruct unpacker.
    Use an unpacker (e.g., accelerometry), and stick in a data dict, then compare
    the resulting bit pattern vs the table in the spec. Use values such as 0xFFFF
    or 0xFFFF-2 to see where the different bits of a value land.
    """
    # use an unpacker put your bits here
    packed = reverse_bits8(unpacker.pack(datadict))
    # print the bytes
    print(' '.join([f'{k:02d} {v:08b}\n' for k, v in enumerate(packed)]))
