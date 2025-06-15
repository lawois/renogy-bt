# -*- coding: utf-8 -*-
"""
renogybt.ConfigManager
~~~~~~~~~~~~~~~~~~~~~~

This module provides the `ConfigManager` class, responsible for loading,
validating, and providing access to configuration settings from an INI file
(typically `config.ini`).

It ensures that required sections and keys are present, offering a centralized
way for other modules in the library to retrieve configuration values.
"""
import configparser
import os
import logging
from typing import Optional # Import Optional
from . import constants as C

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages loading and access to configuration settings from an INI file.

    The ConfigManager reads a specified INI file, validates its structure against
    a predefined set of required sections and keys, and provides a simple `get`
    method to retrieve configuration values.

    Args:
        config_file (str, optional): The path to the configuration file.
            Defaults to "config.ini".

    Raises:
        FileNotFoundError: If the specified `config_file` does not exist.
        ValueError: If required sections or keys are missing from the config file.
    """

    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()
        self._validate_config()

    def _load_config(self):
        """Loads the configuration file.

        Raises:
            FileNotFoundError: If the configuration file is not found.
        """
        if not os.path.exists(self.config_file):
            logger.error(f"Configuration file '{self.config_file}' not found.")
            raise FileNotFoundError(
                f"Configuration file '{self.config_file}' not found."
            )
        self.config.read(self.config_file)
        logger.info(f"Configuration file '{self.config_file}' loaded successfully.")

    def _validate_config(self):
        """Validates that required sections and keys are present in the config.

        Raises:
            ValueError: If a required section or key is missing.
        """
        logger.debug(f"Validating configuration from '{self.config_file}'...")
        required_sections = {
            C.CONFIG_SECTION_DEVICE: [
                C.CONFIG_KEY_MAC_ADDR,
                C.CONFIG_KEY_ALIAS,
                C.CONFIG_KEY_TYPE,
                C.CONFIG_KEY_DEVICE_ID,
                C.CONFIG_KEY_CONNECT_RETRIES,
                C.CONFIG_KEY_CONNECT_RETRY_DELAY,
            ],
            C.CONFIG_SECTION_DATA: [
                C.CONFIG_KEY_ENABLE_POLLING,
                C.CONFIG_KEY_POLL_INTERVAL,
                C.CONFIG_KEY_FIELDS,
                C.CONFIG_KEY_TEMP_UNIT,
                C.CONFIG_KEY_LOG_LEVEL,
            ],
            C.CONFIG_SECTION_REMOTE_LOGGING: [
                C.CONFIG_KEY_RL_ENABLED,
                C.CONFIG_KEY_RL_URL,
                C.CONFIG_KEY_RL_AUTH_HEADER,
            ],
            C.CONFIG_SECTION_MQTT: [
                C.CONFIG_KEY_MQTT_ENABLED,
                C.CONFIG_KEY_MQTT_SERVER,
                C.CONFIG_KEY_MQTT_PORT,
                C.CONFIG_KEY_MQTT_TOPIC,
                C.CONFIG_KEY_MQTT_USER,
                C.CONFIG_KEY_MQTT_PASSWORD,
            ],
            C.CONFIG_SECTION_PVOUTPUT: [
                C.CONFIG_KEY_PV_ENABLED,
                C.CONFIG_KEY_PV_API_KEY,
                C.CONFIG_KEY_PV_SYSTEM_ID,
            ],
        }

        for section, keys in required_sections.items():
            if not self.config.has_section(section):
                msg = f"Missing required section '[{section}]' in config file '{self.config_file}'."
                logger.error(msg)
                raise ValueError(msg)
            for key in keys:
                if not self.config.has_option(section, key):
                    msg = f"Missing required key '{key}' in section '[{section}]' in config file '{self.config_file}'."
                    logger.error(msg)
                    raise ValueError(msg)
        logger.info("Configuration file validation successful.")

    def get(self, section: str, key: str, fallback: Optional[any] = None) -> Optional[str]:
        """
        Retrieves a configuration value.

        Args:
            section: The section name in the INI file.
            key: The key name within the section.
            fallback: An optional fallback value to return if the key is not found.
                      Defaults to None.

        Returns:
            The configuration value as a string, or the fallback value if provided
            and the key is not found. Returns None if the key is not found and
            no fallback is specified.
        """
        return self.config.get(section, key, fallback=fallback)


if __name__ == "__main__":
    # This block is for example purposes and direct testing of ConfigManager.
    # It sets up a temporary basic logger to see ConfigManager's own logging.
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info(
        "Running ConfigManager example (typically not run directly in application)"
    )

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
    config_file_name = "config.ini.example"  # Use a different name to avoid conflicts
    with open(config_file_name, "w") as f:
        f.write(dummy_config_content)

    try:
        config_manager = ConfigManager(config_file=config_file_name)
        print(f"\n--- Example Config Values (from {config_file_name}) ---")
        print(
            f"Device MAC Address: {config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_MAC_ADDR)}"
        )
        print(
            f"Device Alias: {config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS)}"
        )
        print(
            f"Connect Retries: {config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRIES)}"
        )
        print(
            f"Polling enabled: {config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING)}"
        )
        print(
            f"Log Level: {config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_LOG_LEVEL)}"
        )
        print(
            f"MQTT server: {config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_SERVER)}"
        )
        print("--- End Example Config Values ---")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error in ConfigManager __main__ example: {e}", exc_info=True)
    finally:
        if os.path.exists(config_file_name):
            os.remove(config_file_name)
            logger.info(f"Cleaned up example config file: {config_file_name}")
