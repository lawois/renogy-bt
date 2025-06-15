import unittest
from unittest.mock import MagicMock, patch
from renogybt.RoverClient import RoverClient, FUNCTION_MAP, CHARGING_STATE_MAP, LOAD_STATE_MAP, BATTERY_TYPE_MAP
from renogybt.datamodels import RoverData
from renogybt.ConfigManager import ConfigManager # Needed for instantiation
from renogybt import constants as C

class TestRoverClientParsing(unittest.TestCase):

    def setUp(self):
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        # Provide return values for all config keys accessed by RoverClient and its BaseClient constructor
        self.mock_config_manager.get.side_effect = lambda section, key, fallback=None: {
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_MAC_ADDR): "XX:XX:XX:XX:XX:XX",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS): "TestRover",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_DEVICE_ID): "1",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRIES): "3",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRY_DELAY): "5",
            (C.CONFIG_SECTION_DATA, C.CONFIG_KEY_TEMP_UNIT): "C", # Used in parse_charging_info
        }.get((section, key), fallback if fallback is not None else "default_value_for_test")


        # Patch the superclass's parsing methods for these tests, as they are tested separately
        with patch.object(RoverClient, '_parse_device_info') as mock_super_dev_info, \
             patch.object(RoverClient, '_parse_device_address') as mock_super_dev_addr:

            self.client = RoverClient(config_manager=self.mock_config_manager)
            # Ensure data object is a fresh RoverData instance for each test method
            self.client.data = RoverData()

            # Store mocks if needed for assertion (optional here as we don't check their calls)
            self.mock_super_dev_info = mock_super_dev_info
            self.mock_super_dev_addr = mock_super_dev_addr


    def test_parse_charging_info(self):
        """Test parsing of the main charging information block."""
        # Construct sample byte array (bs) for parse_charging_info
        # Example: 34 words = 68 bytes. Response starts with ID, func, byte_count.
        # Data payload starts after that. `bytes_to_int` offsets are from start of `bs`.
        # Let's assume `bs` is the full response frame for now.
        # For simplicity, only populating a few key fields.
        # Example: Bat % = 80 (0x0050), Bat V = 12.5V (0x007D), Bat Curr = 5.5A (0x0226)
        # Controller Temp = 25C (raw 25), PV V = 17.5V (0x00AF), PV Curr = 3.0A (0x012C)
        # Load Status = ON (bit 7 of byte at offset 67 set)
        # Charging Status = MPPT (2) (byte at offset 68)

        # Frame: DeviceID(1), Func(1), ByteCount(1), Data(68), CRC(2) = 73 bytes
        # Data part starts at index 3 of the frame.
        # bytes_to_int(bs, offset, length) uses absolute offsets in bs.

        response_frame = bytearray(73)
        response_frame[0] = 1  # Device ID
        response_frame[1] = C.OP_CODE_READ # Function Code
        response_frame[2] = 68 # Byte count for data part

        # Populate data for RoverData fields (offsets are into the full response_frame)
        # Battery Percentage (offset 3, 2 bytes): 80% -> 0x0050
        response_frame[3:5] = b'\x00\x50'
        # Battery Voltage (offset 5, 2 bytes, scale 0.1): 12.5V -> 125 -> 0x007D
        response_frame[5:7] = b'\x00\x7D'
        # Battery Current (offset 7, 2 bytes, scale 0.01): 5.5A -> 550 -> 0x0226
        response_frame[7:9] = b'\x02\x26'
        # Controller Temp (offset 9, 1 byte, raw C): 25C
        response_frame[9] = 25
        # Battery Temp (offset 10, 1 byte, raw C): 26C
        response_frame[10] = 26
        # Load Voltage (offset 11, 2 bytes, scale 0.1): 12.0V -> 120 -> 0x0078
        response_frame[11:13] = b'\x00\x78'
        # PV Voltage (offset 17, 2 bytes, scale 0.1): 17.5V -> 175 -> 0x00AF
        response_frame[17:19] = b'\x00\xAF'
        # Load Status (offset 67, 1 byte, bit 7 for ON): 0x80 for ON
        response_frame[67] = 0x80
        # Charging Status (offset 68, 1 byte): 2 for MPPT
        response_frame[68] = 2

        self.client.parse_charging_info(response_frame)

        self.assertEqual(self.client.data.battery_percentage, 80)
        self.assertAlmostEqual(self.client.data.battery_voltage, 12.5)
        self.assertAlmostEqual(self.client.data.battery_current, 5.50)
        self.assertAlmostEqual(self.client.data.controller_temperature, 25.0)
        self.assertAlmostEqual(self.client.data.pv_voltage, 17.5)
        self.assertEqual(self.client.data.load_status, "on") # from LOAD_STATE_MAP
        self.assertEqual(self.client.data.charging_status, "mppt") # from CHARGING_STATE_MAP

    def test_parse_battery_type(self):
        """Test parsing of the battery type."""
        # Frame: DeviceID(1), Func(1), ByteCount(1), Data(2 for 1 word), CRC(2) = 7 bytes
        response_frame = bytearray(7)
        response_frame[0] = 1
        response_frame[1] = C.OP_CODE_READ
        response_frame[2] = 2 # 1 word = 2 bytes
        # Battery Type (offset 3, 2 bytes): 4 for Lithium
        response_frame[3:5] = b'\x00\x04'

        self.client.parse_battery_type(response_frame)
        self.assertEqual(self.client.data.battery_type, "lithium") # from BATTERY_TYPE_MAP

    def test_parse_set_load_response(self):
        """Test parsing the response from a set_load command."""
        # Frame: DeviceID(1), Func(1), StartAddr_H(1), StartAddr_L(1), Value_H(1), Value_L(1), CRC(2) = 8 bytes
        # Example: response to setting load ON (value 1)
        response_frame = bytearray(8)
        response_frame[0] = 1
        response_frame[1] = C.OP_CODE_WRITE # Write function code
        response_frame[4:6] = b'\x00\x01' # Echo back the value written (e.g. 1 for ON)

        parsed_response = self.client.parse_set_load_response(response_frame)
        self.assertEqual(parsed_response.get(C.KEY_FUNCTION), "WRITE")
        self.assertEqual(parsed_response.get('load_set_status'), "on") # from LOAD_STATE_MAP

if __name__ == '__main__':
    unittest.main()
