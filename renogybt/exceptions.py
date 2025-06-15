class RenogyBTError(Exception):
    """Base exception class for renogybt."""
    pass

class DeviceNotFoundError(RenogyBTError):
    """Raised when the Bluetooth device cannot be found."""
    pass

class ConnectionError(RenogyBTError):
    """Raised when there is an error connecting to the Bluetooth device."""
    pass

class ReadTimeoutError(RenogyBTError):
    """Raised when a read operation times out."""
    pass

class InvalidResponseError(RenogyBTError):
    """Raised when the device provides an invalid or unexpected response."""
    pass

class ConfigError(RenogyBTError):
    """Raised for configuration related errors."""
    pass
