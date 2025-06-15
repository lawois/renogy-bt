import configparser
import os
import configparser
import os
import logging # Import logging
from . import constants as C

logger = logging.getLogger(__name__) # Module-level logger

class ConfigManager:
    def __init__(self, config_file='config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()
        self._validate_config()

    def _load_config(self):
        if not os.path.exists(self.config_file):
            logger.error(f"Configuration file {self.config_file} not found.")
            raise FileNotFoundError(f"Configuration file {self.config_file} not found.")
        self.config.read(self.config_file)
        logger.info(f"Configuration file {self.config_file} loaded successfully.")

    def _validate_config(self):
        required_sections = {
            C.CONFIG_SECTION_DEVICE: [
                C.CONFIG_KEY_MAC_ADDR, C.CONFIG_KEY_ALIAS, C.CONFIG_KEY_TYPE,
                C.CONFIG_KEY_DEVICE_ID, C.CONFIG_KEY_CONNECT_RETRIES, C.CONFIG_KEY_CONNECT_RETRY_DELAY
            ],
            C.CONFIG_SECTION_DATA: [
                C.CONFIG_KEY_ENABLE_POLLING, C.CONFIG_KEY_POLL_INTERVAL, C.CONFIG_KEY_FIELDS,
                C.CONFIG_KEY_TEMP_UNIT, C.CONFIG_KEY_LOG_LEVEL # Added LOG_LEVEL
            ],
            C.CONFIG_SECTION_REMOTE_LOGGING: [
                C.CONFIG_KEY_RL_ENABLED, C.CONFIG_KEY_RL_URL, C.CONFIG_KEY_RL_AUTH_HEADER
            ],
            C.CONFIG_SECTION_MQTT: [
                C.CONFIG_KEY_MQTT_ENABLED, C.CONFIG_KEY_MQTT_SERVER, C.CONFIG_KEY_MQTT_PORT,
                C.CONFIG_KEY_MQTT_TOPIC, C.CONFIG_KEY_MQTT_USER, C.CONFIG_KEY_MQTT_PASSWORD
            ],
            C.CONFIG_SECTION_PVOUTPUT: [
                C.CONFIG_KEY_PV_ENABLED, C.CONFIG_KEY_PV_API_KEY, C.CONFIG_KEY_PV_SYSTEM_ID
            ]
        }

        for section, keys in required_sections.items():
            if not self.config.has_section(section):
                msg = f"Missing '{section}' section in config file {self.config_file}."
                logger.error(msg)
                raise ValueError(msg)
            for key in keys:
                if not self.config.has_option(section, key):
                    # For log_level, we can provide a default if it's missing, so it's not strictly "required" to exist.
                    # However, for this example, let's assume if [data] section exists, log_level should be there.
                    # A more robust approach might be to fetch it with a default value later.
                    msg = f"Missing '{key}' in '{section}' section in config file {self.config_file}."
                    logger.error(msg)
                    raise ValueError(msg)
        logger.debug("Config file validation successful.")

    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)


if __name__ == '__main__':
    # Example usage:
    # Create a dummy config.ini for testing
    # Note: Constants are not available in this __main__ block unless this file is run as a module
    # and constants.py is in the python path. For direct script run, these would be string literals.
    # However, the ConfigManager class itself will use the imported C when instantiated from elsewhere.
    dummy_config_content = f"""
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
{C.CONFIG_KEY_MQTT_USER} =
{C.CONFIG_KEY_MQTT_PASSWORD} =

[{C.CONFIG_SECTION_PVOUTPUT}]
{C.CONFIG_KEY_PV_ENABLED} = false
{C.CONFIG_KEY_PV_API_KEY} = your_api_key
{C.CONFIG_KEY_PV_SYSTEM_ID} = your_system_id
"""
    config_file_name = 'config.ini'
    with open(config_file_name, 'w') as f:
        f.write(dummy_config_content)

    try:
        # When ConfigManager is instantiated, it will use the imported C internally.
        config_manager = ConfigManager(config_file=config_file_name)
        print(f"Device MAC Address: {config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_MAC_ADDR)}")
        print(f"Device Alias: {config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS)}")
        print(f"Connect Retries: {config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRIES)}")
        print(f"Polling enabled: {config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING)}")
        print(f"Log Level: {config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_LOG_LEVEL)}")
        print(f"MQTT server: {config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_SERVER)}")
    except (FileNotFoundError, ValueError) as e:
        # In a real app, logger from main script would catch this.
        # For this example, just print.
        print(f"Error in ConfigManager __main__: {e}")
    finally:
        if os.path.exists(config_file_name):
            os.remove(config_file_name)
