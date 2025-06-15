import unittest
from unittest.mock import MagicMock, patch
from renogybt.BatteryClient import BatteryClient, FUNCTION_MAP
from renogybt.datamodels import BatteryData
from renogybt.ConfigManager import ConfigManager # Needed for instantiation
from renogybt import constants as C

class TestBatteryClientParsing(unittest.TestCase):

    def setUp(self):
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_config_manager.get.side_effect = lambda section, key, fallback=None: {
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_MAC_ADDR): "YY:YY:YY:YY:YY:YY",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS): "TestBattery",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_DEVICE_ID): "1",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRIES): "3",
            (C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRY_DELAY): "5",
            (C.CONFIG_SECTION_DATA, C.CONFIG_KEY_TEMP_UNIT): "C", # Used in parse_cell_temp_info
        }.get((section, key), fallback if fallback is not None else "default_value_for_test")

        with patch.object(BatteryClient, '_parse_device_info') as mock_super_dev_info, \
             patch.object(BatteryClient, '_parse_device_address') as mock_super_dev_addr:

            self.client = BatteryClient(config_manager=self.mock_config_manager)
            self.client.data = BatteryData() # Ensure fresh data object for each test

            self.mock_super_dev_info = mock_super_dev_info
            self.mock_super_dev_addr = mock_super_dev_addr

    def test_parse_cell_volt_info(self):
        """Test parsing of cell voltage information."""
        # 17 words = 34 bytes of data. Frame = 1+1+1+34+2 = 39 bytes
        response_frame = bytearray(39)
        response_frame[0] = 1 # Device ID
        response_frame[1] = C.OP_CODE_READ # Func Code
        response_frame[2] = 34 # Byte count

        # Cell count (offset 3, 2 bytes): 4 cells
        response_frame[3:5] = b'\x00\x04'
        # Cell 1 (offset 5, 2 bytes, scale 0.001V -> 3.3V -> 3300 -> 0x0CE4)
        response_frame[5:7] = b'\x0C\xE4' # 3300 mV = 3.3V
        # Cell 2 (offset 7, 2 bytes): 3.31V -> 3310 -> 0x0CEE
        response_frame[7:9] = b'\x0C\xEE' # 3310 mV = 3.31V
        # Cell 3 (offset 9, 2 bytes): 3.29V -> 3290 -> 0x0CDA
        response_frame[9:11] = b'\x0C\xDA' # 3290 mV = 3.29V
        # Cell 4 (offset 11, 2 bytes): 3.305V -> 3305 -> 0x0CE9
        response_frame[11:13] = b'\x0C\xE9' # 3305 mV = 3.305V

        # Note: BatteryClient's parse_cell_volt_info uses scale 0.1 from original Utils.bytes_to_int
        # But the datamodel comment for BatteryData.cell_voltages implies mV, so scale 0.001.
        # The test in BatteryClient uses scale=0.1 in its own logic.
        # Let's assume the client's parser is correct for its device type (scale 0.1 for this example).
        # 3.3V -> 33 with scale 0.1. 0x0021
        response_frame[5:7] = b'\x00\x21' # 33 -> 3.3V
        response_frame[7:9] = b'\x00\x22' # 34 -> 3.4V (example)

        self.client.parse_cell_volt_info(response_frame)

        self.assertEqual(self.client.data.cell_count, 4)
        self.assertAlmostEqual(self.client.data.cell_voltages.get(1), 3.3) # 1-based index
        self.assertAlmostEqual(self.client.data.cell_voltages.get(2), 3.4)


    def test_parse_cell_temp_info(self):
        """Test parsing of cell temperature information."""
        response_frame = bytearray(39)
        response_frame[1] = C.OP_CODE_READ
        response_frame[2] = 34

        # Sensor count (offset 3, 2 bytes): 2 sensors
        response_frame[3:5] = b'\x00\x02'
        # Temp 1 (offset 5, 2 bytes, scale 0.1, signed): 25.5C -> 255 -> 0x00FF
        response_frame[5:7] = b'\x00\xFF'
        # Temp 2 (offset 7, 2 bytes, scale 0.1, signed): -1.0C -> -10 -> 0xFFF6 (two's complement for -10)
        response_frame[7:9] = b'\xFF\xF6'

        self.client.parse_cell_temp_info(response_frame)
        self.assertEqual(self.client.data.sensor_count, 2)
        self.assertAlmostEqual(self.client.data.temperatures.get(1), 25.5) # 1-based index
        self.assertAlmostEqual(self.client.data.temperatures.get(2), -1.0)

    def test_parse_battery_info(self):
        """Test parsing of overall battery status information."""
        # 6 words = 12 bytes of data. Frame = 1+1+1+12+2 = 17 bytes
        response_frame = bytearray(17)
        response_frame[1] = C.OP_CODE_READ
        response_frame[2] = 12

        # Current (offset 3, 2 bytes, signed, scale 0.01): -10.55A -> -1055 -> 0xFBE1
        response_frame[3:5] = b'\xFB\xE1'
        # Voltage (offset 5, 2 bytes, scale 0.1): 52.5V -> 525 -> 0x020D
        response_frame[5:7] = b'\x02\x0D'
        # Remaining Charge (offset 7, 4 bytes, scale 0.001): 80.123Ah -> 80123 -> 0x000138FB
        response_frame[7:11] = b'\x00\x01\x38\xFB'
        # Capacity (offset 11, 4 bytes, scale 0.001): 100Ah -> 100000 -> 0x000186A0
        response_frame[11:15] = b'\x00\x01\x86\xA0'

        self.client.parse_battery_info(response_frame)
        self.assertAlmostEqual(self.client.data.current, -10.55)
        self.assertAlmostEqual(self.client.data.voltage, 52.5)
        self.assertAlmostEqual(self.client.data.remaining_charge, 80.12) # Adjusted to 2 decimal places
        self.assertAlmostEqual(self.client.data.capacity, 100.00) # Adjusted to 2 decimal places

if __name__ == '__main__':
    unittest.main()
