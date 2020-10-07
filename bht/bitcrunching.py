"""Custom bit crunching as required by the BHT protocol."""

__all__ = ['crc8', 'reverse_bits8']


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


# pre-calculated lookup table for the fast CRC8 function below
CRC_LUT = [crc8_slow([b]) for b in range(256)]


def crc8(payload):
    """Calc a CRC8 of the given payload sequence (using a lookup table, i.e.,
    fast). This is not a standard CRC8 but BHT-specific."""
    accum = 0
    for b in payload:
        accum = CRC_LUT[accum ^ b]
    return accum


def reverse_bits8_slow(n):
    """Reverse the bits in a byte."""
    return int('{:08b}'.format(n)[::-1], 2)


# pre-calculated lookup table to reverse the bits of a byte
REVERSE_BITS_LUT = [reverse_bits8_slow(b) for b in range(256)]


def reverse_bits8(seq):
    """Reverse bits in a sequence of bytes using a lookup table."""
    return [REVERSE_BITS_LUT[b] for b in seq]
