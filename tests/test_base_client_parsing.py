import unittest
from unittest.mock import MagicMock
from renogybt.BaseClient import BaseClient
from renogybt import constants as C

# A minimal dataclass for testing if BaseClient methods set attributes
class MockDataContainer:
    def __init__(self):
        self.model = None
        self.device_id = None
        # Add any other fields that might be touched by parsing methods if necessary

class TestBaseClientParsing(unittest.TestCase):

    def setUp(self):
        """Set up a BaseClient instance with a mock ConfigManager."""
        self.mock_config_manager = MagicMock()
        # Configure mock_config_manager to return necessary values if BaseClient.__init__ uses them
        self.mock_config_manager.get.side_effect = lambda section, key, fallback=None: {
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_DEVICE_ID): "1", # Modbus ID from config
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_MAC_ADDR): "XX:XX:XX:XX:XX:XX",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS): "TestDeviceAlias",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRIES): "3",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRY_DELAY): "5",
        }.get((section, key), fallback)

        self.client = BaseClient(config_manager=self.mock_config_manager)
        # Replace the client's data attribute with our simple mock container for these tests
        self.client.data = MockDataContainer()


    def test_parse_device_info_simple(self):
        """Test _parse_device_info with a simple model string."""
        # Example response bytes:
        # Byte 0: Device ID (e.g., 1)
        # Byte 1: Function Code (e.g., 3 for read)
        # Byte 2: Byte count (e.g., 16 for model string if it's 16 chars)
        # Byte 3-18: Model string ("RNG-CTRL-RVR40 ")
        # ... CRC bytes
        response_bytes = bytes([1, 3, 16]) + b"RNG-CTRL-RVR40  " + bytes([0,0]) # Dummy CRC
        model_start_index = 3
        model_end_index = model_start_index + 16 # Model is 16 bytes "RNG-CTRL-RVR40  "

        self.client._parse_device_info(response_bytes, model_start_index, model_end_index)
        self.assertEqual(self.client.data.model, "RNG-CTRL-RVR40") # strip() should remove trailing spaces

    def test_parse_device_info_with_null_chars(self):
        """Test _parse_device_info with null characters to be stripped."""
        response_bytes = bytes([1, 3, 10]) + b"TESTMDL\x00\x00\x00" + bytes([0,0])
        model_start_index = 3
        model_end_index = model_start_index + 10

        self.client._parse_device_info(response_bytes, model_start_index, model_end_index, strip_chars='\x00')
        self.assertEqual(self.client.data.model, "TESTMDL")

    def test_parse_device_info_empty(self):
        """Test _parse_device_info with an empty model string part."""
        response_bytes = bytes([1, 3, 0]) + bytes([0,0]) # Zero length model string
        model_start_index = 3
        model_end_index = 3

        self.client._parse_device_info(response_bytes, model_start_index, model_end_index)
        self.assertEqual(self.client.data.model, "")

    def test_parse_device_info_unicode_error(self):
        """Test _parse_device_info with bytes that don't form valid UTF-8."""
        response_bytes = bytes([1, 3, 5]) + b"\xff\xfe\xfd\xfc\xfb" + bytes([0,0]) # Invalid UTF-8 sequence
        model_start_index = 3
        model_end_index = model_start_index + 5

        # Expecting it to log a warning and set model to "Unknown"
        with self.assertLogs(level='WARNING') as log:
            self.client._parse_device_info(response_bytes, model_start_index, model_end_index)
        self.assertEqual(self.client.data.model, "Unknown")
        self.assertTrue(any("Could not decode model string" in message for message in log.output))


    def test_parse_device_address_one_byte(self):
        """Test _parse_device_address for a 1-byte device ID."""
        # Example response: [..., Addr_High, Addr_Low, ID_High, ID_Low, ...]
        # If ID is at offset 4, and is 1 byte:
        # Response: [FuncCode, ByteCount, Reg_Addr_H, Reg_Addr_L, ID_val, CRC_H, CRC_L] (example for a read response)
        # Let's assume response_bytes is the full frame, and address_start_index points correctly.
        response_bytes = bytes([1, 3, 2, 0, 5, 0, 0]) # ID=5 at offset 4
        address_start_index = 4 # Start of ID byte
        address_length_bytes = 1

        self.client._parse_device_address(response_bytes, address_start_index, address_length_bytes)
        self.assertEqual(self.client.data.device_id, 5)

    def test_parse_device_address_two_bytes(self):
        """Test _parse_device_address for a 2-byte device ID (less common for this field)."""
        # Example: ID = 258 (0x0102)
        # Response: [..., ID_Byte1, ID_Byte2, ...] where ID_Byte1 is MSB if big-endian
        response_bytes = bytes([1, 3, 2, 1, 2, 0, 0]) # ID=0x0102=258 at offset 3, length 2
        address_start_index = 3
        address_length_bytes = 2 # Big-endian by default in bytes_to_int if length > 0

        self.client._parse_device_address(response_bytes, address_start_index, address_length_bytes)
        self.assertEqual(self.client.data.device_id, 258) # 0x0102

    def test_parse_device_address_id_mismatch_warning(self):
        """Test that a warning is logged if parsed device ID differs from config."""
        self.client.device_id_from_config = 1 # Set ID from config

        response_bytes = bytes([1, 3, 2, 0, 5, 0, 0]) # Parsed ID will be 5
        address_start_index = 4
        address_length_bytes = 1

        with self.assertLogs(level='WARNING') as log:
            self.client._parse_device_address(response_bytes, address_start_index, address_length_bytes)

        self.assertEqual(self.client.data.device_id, 5)
        self.assertTrue(any("Device ID mismatch" in message for message in log.output))


if __name__ == '__main__':
    unittest.main()
