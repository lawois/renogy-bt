# -*- coding: utf-8 -*-
"""
renogybt.exceptions
~~~~~~~~~~~~~~~~~~~

This module defines custom exception classes used by the Renogy BT/BLE client library.
These exceptions allow for more specific error handling by applications using the library.
All custom exceptions inherit from the base `RenogyBTError`.
"""


class RenogyBTError(Exception):
    """
    Base exception class for all errors raised by the Renogy BT/BLE library.

    Catching this exception will catch any error originating from this library,
    allowing for generic error handling if specific cases are not needed.
    """

    pass


class DeviceNotFoundError(RenogyBTError):
    """
    Raised when a specified Bluetooth device cannot be found during discovery.

    This typically means the device is not advertising, is out of range,
    or the provided MAC address or alias in the configuration is incorrect.
    """

    pass


class ConnectionError(RenogyBTError):
    """
    Raised when there is an error connecting to an already discovered Bluetooth device.

    This can occur due to various reasons, such as the device refusing the connection,
    signal interference, or issues with the Bluetooth adapter.
    """

    pass


class ReadTimeoutError(RenogyBTError):
    """
    Raised when a read operation does not complete within the expected timeframe.

    This usually indicates a communication problem with the device, where it
    failed to send a response to a command.
    """

    pass


class InvalidResponseError(RenogyBTError):
    """
    Raised when the device provides an invalid or unexpected response.

    This could be due to:
    - Response length not matching the expected length.
    - Data failing CRC checks (if implemented).
    - Unexpected operation codes or malformed data packets.
    - Errors during the parsing of the response data.
    """

    pass


class ConfigError(RenogyBTError):
    """
    Raised for configuration-related errors.

    While `ConfigManager` currently raises `ValueError` for most validation issues
    as per its docstring, this exception is available if more specific
    configuration errors from the library need to be distinguished.
    For example, if a required configuration section or key is missing and
    `ValueError` is too generic.
    """

    pass
