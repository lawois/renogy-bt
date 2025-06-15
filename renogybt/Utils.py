# -*- coding: utf-8 -*-
"""
renogybt.Utils
~~~~~~~~~~~~~~

This module provides utility functions for the Renogy BT/BLE client library,
including data conversion (bytes to int, int to bytes), temperature parsing,
data filtering, and CRC calculation for Modbus-like communication.
"""

# Reads data from a list of bytes, and converts to an int
def bytes_to_int(
    byte_array: bytes, offset: int, length: int, signed: bool = False, scale: float = 1
) -> float:
    """
    Converts a segment of a byte array to an integer or float, applying a scaling factor.

    Args:
        byte_array: The input byte array (or list of bytes).
        offset: The starting index of the byte segment.
        length: The number of bytes to convert. If positive, big-endian is used.
                If negative, little-endian is used (length becomes abs(length)).
        signed: Whether the integer representation is signed. Defaults to False.
        scale: A scaling factor to apply to the integer value. Defaults to 1.
               The result is rounded to 2 decimal places if scaling is applied.

    Returns:
        The converted numerical value (float if scaled, otherwise int, though
        current implementation rounds and returns float for scaled values).
        Returns 0 if the specified segment is out of bounds.
    """
    ret = 0
    actual_length = abs(length)

    if len(byte_array) < (offset + actual_length):
        # Not enough bytes in array for specified offset and length
        return float(ret)  # Return float for consistency

    if length > 0:  # Big-endian
        byteorder = "big"
        start = offset
        end = offset + actual_length
    else:  # Little-endian
        byteorder = "little"
        start = offset
        end = offset + actual_length
        # Original little-endian logic was a bit confusing;
        # standard int.from_bytes handles little-endian correctly with positive length.
        # Re-interpreting 'length < 0' to just mean little-endian.
        # The original slice `bs[offset + length + 1 : offset + 1]` was for `length` being negative.
        # With actual_length, it's simpler: bs[start:end]

    try:
        val = int.from_bytes(
            byte_array[start:end], byteorder=byteorder, signed=signed
        )
    except TypeError: # if byte_array is a list of ints instead of bytes
        val = int.from_bytes(
            bytes(byte_array[start:end]), byteorder=byteorder, signed=signed
        )


    if scale != 1:
        return round(val * scale, 2)
    return float(val) # Return float for consistency, even if not scaled


def int_to_bytes(value: int, position: int = 0) -> int:
    """
    Converts a 16-bit integer into its high or low byte.

    Args:
        value: The 16-bit integer to convert.
        pos: The position of the byte to return (0 for high byte, 1 for low byte).
             Defaults to 0.

    Returns:
        The integer value of the specified byte (0-255).
        Returns 0 if an invalid position is given.
    """
    # Ensure value is treated as a 16-bit unsigned integer for formatting
    # This means negative numbers will be represented by their two's complement form
    # truncated to 16 bits if they were originally larger.
    # For typical Modbus usage, registers are often treated as unsigned short.
    if not 0 <= value <= 0xFFFF:
        # Handle out-of-range values if necessary, or assume they are masked appropriately.
        # For simplicity, let's assume value fits or is meant to be truncated.
        pass

    binary_representation = format(value & 0xFFFF, "016b")  # Mask to 16 bits

    if position == 0:  # High byte
        return int(binary_representation[:8], 2)
    if position == 1:  # Low byte
        return int(binary_representation[8:], 2)
    return 0  # Invalid position


def parse_temperature(raw_value: int, unit: str) -> float:
    """
    Parses a raw temperature value from a Renogy device.

    The temperature is often encoded with the 7th bit as a sign bit.
    Bit 7 (0x80): Sign bit (1 for negative, 0 for positive)
    Bits 0-6: Temperature magnitude

    Args:
        raw_value: The raw byte value from the device.
        unit: The desired temperature unit ("C" for Celsius, "F" for Fahrenheit).

    Returns:
        The temperature in the specified unit, as a float.
    """
    sign = raw_value >> 7
    magnitude = raw_value & 0x7F  # Mask out the sign bit to get magnitude
    celsius = -magnitude if sign == 1 else magnitude
    return format_temperature(celsius, unit)


def format_temperature(celsius: float, unit: str = "F") -> float:
    """
    Converts Celsius temperature to Fahrenheit if requested.

    Args:
        celsius: The temperature in Celsius.
        unit: The desired output unit. "F" for Fahrenheit, otherwise Celsius.
              Defaults to "F".

    Returns:
        The temperature in the specified unit, rounded to 2 decimal places.
    """
    if unit.strip().upper() == "F":
        return round((celsius * 9 / 5) + 32, 2)
    return round(celsius, 2)


def filter_fields(data: dict, fields_str: str) -> dict:
    """
    Filters a dictionary to include only specified fields.

    Args:
        data: The input dictionary (e.g., parsed device data).
        fields_str: A comma-separated string of field names to include.
                    If empty or None, the original data dictionary is returned.

    Returns:
        A new dictionary containing only the specified fields, if they exist in the
        original data. If `fields_str` is empty or None, or if no specified
        fields are found, the original data dictionary is returned.
    """
    if not fields_str: # Handle empty or None fields_str
        return data

    fields = [x.strip() for x in fields_str.split(",")]
    if not fields: # Handle cases where fields_str might be like "," or ",,"
        return data

    # Filter to include only keys present in the original data
    filtered_data = {key: data[key] for key in fields if key in data}

    # If no requested fields were found, it might be better to return an empty dict
    # or the original data based on desired behavior. Current ruff-formatted code
    # implies returning original data if the set of fields is not a subset,
    # which might be counter-intuitive for filtering.
    # This version returns only the fields that *are* present.
    # If `fields` contains keys not in `data`, they are simply ignored.
    return filtered_data


# CRC-16 Modbus lookup tables
CRC16_LOW_BYTES = (
    0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2, 0xC6, 0x06, 0x07, 0xC7,
    0x05, 0xC5, 0xC4, 0x04, 0xCC, 0x0C, 0x0D, 0xCD, 0x0F, 0xCF, 0xCE, 0x0E,
    0x0A, 0xCA, 0xCB, 0x0B, 0xC9, 0x09, 0x08, 0xC8, 0xD8, 0x18, 0x19, 0xD9,
    0x1B, 0xDB, 0xDA, 0x1A, 0x1E, 0xDE, 0xDF, 0x1F, 0xDD, 0x1D, 0x1C, 0xDC,
    0x14, 0xD4, 0xD5, 0x15, 0xD7, 0x17, 0x16, 0xD6, 0xD2, 0x12, 0x13, 0xD3,
    0x11, 0xD1, 0xD0, 0x10, 0xF0, 0x30, 0x31, 0xF1, 0x33, 0xF3, 0xF2, 0x32,
    0x36, 0xF6, 0xF7, 0x37, 0xF5, 0x35, 0x34, 0xF4, 0x3C, 0xFC, 0xFD, 0x3D,
    0xFF, 0x3F, 0x3E, 0xFE, 0xFA, 0x3A, 0x3B, 0xFB, 0x39, 0xF9, 0xF8, 0x38,
    0x28, 0xE8, 0xE9, 0x29, 0xEB, 0x2B, 0x2A, 0xEA, 0xEE, 0x2E, 0x2F, 0xEF,
    0x2D, 0xED, 0xEC, 0x2C, 0xE4, 0x24, 0x25, 0xE5, 0x27, 0xE7, 0xE6, 0x26,
    0x22, 0xE2, 0xE3, 0x23, 0xE1, 0x21, 0x20, 0xE0, 0xA0, 0x60, 0x61, 0xA1,
    0x63, 0xA3, 0xA2, 0x62, 0x66, 0xA6, 0xA7, 0x67, 0xA5, 0x65, 0x64, 0xA4,
    0x6C, 0xAC, 0xAD, 0x6D, 0xAF, 0x6F, 0x6E, 0xAE, 0xAA, 0x6A, 0x6B, 0xAB,
    0x69, 0xA9, 0xA8, 0x68, 0x78, 0xB8, 0xB9, 0x79, 0xBB, 0x7B, 0x7A, 0xBA,
    0xBE, 0x7E, 0x7F, 0xBF, 0x7D, 0xBD, 0xBC, 0x7C, 0xB4, 0x74, 0x75, 0xB5,
    0x77, 0xB7, 0xB6, 0x76, 0x72, 0xB2, 0xB3, 0x73, 0xB1, 0x71, 0x70, 0xB0,
    0x50, 0x90, 0x91, 0x51, 0x93, 0x53, 0x52, 0x92, 0x96, 0x56, 0x57, 0x97,
    0x55, 0x95, 0x94, 0x54, 0x9C, 0x5C, 0x5D, 0x9D, 0x5F, 0x9F, 0x9E, 0x5E,
    0x5A, 0x9A, 0x9B, 0x5B, 0x99, 0x59, 0x58, 0x98, 0x88, 0x48, 0x49, 0x89,
    0x4B, 0x8B, 0x8A, 0x4A, 0x4E, 0x8E, 0x8F, 0x4F, 0x8D, 0x4D, 0x4C, 0x8C,
    0x44, 0x84, 0x85, 0x45, 0x87, 0x47, 0x46, 0x86, 0x82, 0x42, 0x43, 0x83,
    0x41, 0x81, 0x80, 0x40,
)

CRC16_HIGH_BYTES = (
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
)


def crc16_modbus(data: bytes) -> bytes:
    """
    Calculates the CRC-16 Modbus checksum for the given data.

    Args:
        data: A bytes object containing the data to checksum.

    Returns:
        A bytes object of length 2, representing the CRC-16 checksum
        (high byte, then low byte).
    """
    crc_high = 0xFF  # Initialize CRC high byte
    crc_low = 0xFF  # Initialize CRC low byte

    for byte_val in data:  # Iterate over each byte in the input data
        index = crc_high ^ int(byte_val)  # XOR high byte with current data byte
        crc_high = crc_low ^ CRC16_HIGH_BYTES[index]
        crc_low = CRC16_LOW_BYTES[index]

    return bytes([crc_high, crc_low])
