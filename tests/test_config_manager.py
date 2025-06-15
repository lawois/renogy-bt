import unittest
import os
import configparser
import re # Import re for re.escape
from renogybt.ConfigManager import ConfigManager
from renogybt import constants as C

# Define a path for a temporary config file for testing
TEST_CONFIG_FILE_PATH = "test_config.ini"

class TestConfigManager(unittest.TestCase):

    def tearDown(self):
        """Clean up any created files after each test."""
        if os.path.exists(TEST_CONFIG_FILE_PATH):
            os.remove(TEST_CONFIG_FILE_PATH)

    def _create_dummy_config_file(self, content):
        """Helper method to create a dummy config file."""
        with open(TEST_CONFIG_FILE_PATH, "w") as f:
            f.write(content)

    def test_successful_loading(self):
        """Test that a valid config file is loaded successfully."""
        dummy_content = f"""
[{C.CONFIG_SECTION_DEVICE}]
{C.CONFIG_KEY_MAC_ADDR} = XX:XX:XX:XX:XX:XX
{C.CONFIG_KEY_ALIAS} = TestDevice
{C.CONFIG_KEY_TYPE} = {C.DEVICE_TYPE_ROVER}
{C.CONFIG_KEY_DEVICE_ID} = 1
{C.CONFIG_KEY_CONNECT_RETRIES} = 3
{C.CONFIG_KEY_CONNECT_RETRY_DELAY} = 5

[{C.CONFIG_SECTION_DATA}]
{C.CONFIG_KEY_ENABLE_POLLING} = true
{C.CONFIG_KEY_POLL_INTERVAL} = 60
{C.CONFIG_KEY_FIELDS} = battery_voltage,pv_voltage
{C.CONFIG_KEY_TEMP_UNIT} = C
{C.CONFIG_KEY_LOG_LEVEL} = INFO

[{C.CONFIG_SECTION_REMOTE_LOGGING}]
{C.CONFIG_KEY_RL_ENABLED} = false
{C.CONFIG_KEY_RL_URL} = http://example.com/log
{C.CONFIG_KEY_RL_AUTH_HEADER} = some_token

[{C.CONFIG_SECTION_MQTT}]
{C.CONFIG_KEY_MQTT_ENABLED} = false
{C.CONFIG_KEY_MQTT_SERVER} = mqtt.example.com
{C.CONFIG_KEY_MQTT_PORT} = 1883
{C.CONFIG_KEY_MQTT_TOPIC} = renogy/data
{C.CONFIG_KEY_MQTT_USER} = testuser
{C.CONFIG_KEY_MQTT_PASSWORD} = testpass

[{C.CONFIG_SECTION_PVOUTPUT}]
{C.CONFIG_KEY_PV_ENABLED} = false
{C.CONFIG_KEY_PV_API_KEY} = pv_api_key
{C.CONFIG_KEY_PV_SYSTEM_ID} = pv_system_id
"""
        self._create_dummy_config_file(dummy_content)
        try:
            cm = ConfigManager(config_file=TEST_CONFIG_FILE_PATH)
            self.assertIsNotNone(cm)
            # Check a few values
            self.assertEqual(cm.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_MAC_ADDR), "XX:XX:XX:XX:XX:XX")
            self.assertEqual(cm.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_LOG_LEVEL), "INFO")
        except Exception as e:
            self.fail(f"ConfigManager initialization failed with valid config: {e}")

    def test_missing_required_section(self):
        """Test that ValueError is raised if a required section is missing."""
        # Missing [data] section
        dummy_content = f"""
[{C.CONFIG_SECTION_DEVICE}]
{C.CONFIG_KEY_MAC_ADDR} = XX:XX:XX:XX:XX:XX
{C.CONFIG_KEY_ALIAS} = TestDevice
{C.CONFIG_KEY_TYPE} = {C.DEVICE_TYPE_ROVER}
{C.CONFIG_KEY_DEVICE_ID} = 1
{C.CONFIG_KEY_CONNECT_RETRIES} = 3
{C.CONFIG_KEY_CONNECT_RETRY_DELAY} = 5
"""
        self._create_dummy_config_file(dummy_content)
        # Use re.escape for the part of the message that includes special characters
        section_text_to_match = f"'[{C.CONFIG_SECTION_DATA}]'"
        escaped_section_text = re.escape(section_text_to_match)
        expected_regex = f"Missing required section {escaped_section_text} in config file '{re.escape(TEST_CONFIG_FILE_PATH)}'\\."
        with self.assertRaisesRegex(ValueError, expected_regex):
            ConfigManager(config_file=TEST_CONFIG_FILE_PATH)

    def test_missing_required_key(self):
        """Test that ValueError is raised if a required key in a section is missing."""
        # Missing mac_addr in [device] section
        dummy_content = f"""
[{C.CONFIG_SECTION_DEVICE}]
{C.CONFIG_KEY_ALIAS} = TestDevice
{C.CONFIG_KEY_TYPE} = {C.DEVICE_TYPE_ROVER}
{C.CONFIG_KEY_DEVICE_ID} = 1
{C.CONFIG_KEY_CONNECT_RETRIES} = 3
{C.CONFIG_KEY_CONNECT_RETRY_DELAY} = 5

[{C.CONFIG_SECTION_DATA}]
{C.CONFIG_KEY_ENABLE_POLLING} = true
{C.CONFIG_KEY_POLL_INTERVAL} = 60
{C.CONFIG_KEY_FIELDS} = battery_voltage,pv_voltage
{C.CONFIG_KEY_TEMP_UNIT} = C
{C.CONFIG_KEY_LOG_LEVEL} = INFO

[{C.CONFIG_SECTION_REMOTE_LOGGING}]
{C.CONFIG_KEY_RL_ENABLED} = false
{C.CONFIG_KEY_RL_URL} = http://example.com/log
{C.CONFIG_KEY_RL_AUTH_HEADER} = some_token

[{C.CONFIG_SECTION_MQTT}]
{C.CONFIG_KEY_MQTT_ENABLED} = false
{C.CONFIG_KEY_MQTT_SERVER} = mqtt.example.com
{C.CONFIG_KEY_MQTT_PORT} = 1883
{C.CONFIG_KEY_MQTT_TOPIC} = renogy/data
{C.CONFIG_KEY_MQTT_USER} = testuser
{C.CONFIG_KEY_MQTT_PASSWORD} = testpass

[{C.CONFIG_SECTION_PVOUTPUT}]
{C.CONFIG_KEY_PV_ENABLED} = false
{C.CONFIG_KEY_PV_API_KEY} = pv_api_key
{C.CONFIG_KEY_PV_SYSTEM_ID} = pv_system_id
"""
        self._create_dummy_config_file(dummy_content)
        key_text_to_match = f"'{C.CONFIG_KEY_MAC_ADDR}'"
        section_text_to_match = f"'[{C.CONFIG_SECTION_DEVICE}]'"
        expected_regex = (
            f"Missing required key {re.escape(key_text_to_match)} "
            f"in section {re.escape(section_text_to_match)} "
            f"in config file '{re.escape(TEST_CONFIG_FILE_PATH)}'\\."
        )
        with self.assertRaisesRegex(ValueError, expected_regex):
            ConfigManager(config_file=TEST_CONFIG_FILE_PATH)

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for a non-existent config file."""
        with self.assertRaises(FileNotFoundError):
            ConfigManager(config_file="non_existent_config.ini")

    def test_get_value_types(self):
        """Test correct retrieval of different types of values (string, int, boolean)."""
        dummy_content = f"""
[{C.CONFIG_SECTION_DEVICE}]
{C.CONFIG_KEY_MAC_ADDR} = XX:XX:XX:XX:XX:XX
{C.CONFIG_KEY_ALIAS} = TestDevice
{C.CONFIG_KEY_TYPE} = {C.DEVICE_TYPE_ROVER}
{C.CONFIG_KEY_DEVICE_ID} = 1
{C.CONFIG_KEY_CONNECT_RETRIES} = 3
{C.CONFIG_KEY_CONNECT_RETRY_DELAY} = 5

[{C.CONFIG_SECTION_DATA}]
{C.CONFIG_KEY_ENABLE_POLLING} = true
{C.CONFIG_KEY_POLL_INTERVAL} = 60
{C.CONFIG_KEY_FIELDS} = battery_voltage,pv_voltage
{C.CONFIG_KEY_TEMP_UNIT} = C
{C.CONFIG_KEY_LOG_LEVEL} = DEBUG

[{C.CONFIG_SECTION_REMOTE_LOGGING}]
{C.CONFIG_KEY_RL_ENABLED} = false
{C.CONFIG_KEY_RL_URL} = http://example.com/log
{C.CONFIG_KEY_RL_AUTH_HEADER} = some_token

[{C.CONFIG_SECTION_MQTT}]
{C.CONFIG_KEY_MQTT_ENABLED} = false
{C.CONFIG_KEY_MQTT_SERVER} = mqtt.example.com
{C.CONFIG_KEY_MQTT_PORT} = 1883
{C.CONFIG_KEY_MQTT_TOPIC} = renogy/data
{C.CONFIG_KEY_MQTT_USER} = testuser
{C.CONFIG_KEY_MQTT_PASSWORD} = testpass

[{C.CONFIG_SECTION_PVOUTPUT}]
{C.CONFIG_KEY_PV_ENABLED} = false
{C.CONFIG_KEY_PV_API_KEY} = pv_api_key
{C.CONFIG_KEY_PV_SYSTEM_ID} = pv_system_id
"""
        self._create_dummy_config_file(dummy_content)
        cm = ConfigManager(config_file=TEST_CONFIG_FILE_PATH)

        # String value
        self.assertEqual(cm.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS), "TestDevice")

        # Integer value (ConfigParser reads all as string, conversion is done by user)
        self.assertEqual(int(cm.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_DEVICE_ID)), 1)
        self.assertEqual(int(cm.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_POLL_INTERVAL)), 60)

        # Boolean value (ConfigParser reads all as string, conversion is done by user)
        # User typically does .lower() == 'true' or similar
        self.assertEqual(cm.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING), "true")
        self.assertTrue(cm.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING).lower() == "true")

        # Test fallback
        self.assertIsNone(cm.get(C.CONFIG_SECTION_DEVICE, "non_existent_key"))
        self.assertEqual(cm.get(C.CONFIG_SECTION_DEVICE, "non_existent_key", fallback="default"), "default")


if __name__ == '__main__':
    unittest.main()
