# -*- coding: utf-8 -*-
"""
Renogy BT/BLE Client Library - Example Usage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This script demonstrates how to use the `renogybt` library to connect to a
Renogy device, retrieve data, and handle potential errors. It showcases:
- Loading configuration using `ConfigManager`.
- Setting up logging based on configuration.
- Defining callbacks for data reception and errors.
- Instantiating and starting a specific device client (e.g., `RoverClient`).
- Handling different types of data received (dataclasses for reads, dicts for writes).
- Logging data to various outputs via `DataLogger`.

Usage:
    python example.py [config_file.ini]

If `config_file.ini` is not provided, it defaults to `config.ini` in the same
directory as the script. Ensure your `config.ini` is correctly set up with
your device's MAC address, type, and any desired logging options.
"""
import logging
import os
import sys
import dataclasses # For dataclass checks and conversion
from typing import Any, Union, Optional # Added Optional

from renogybt import (
    DCChargerClient,
    InverterClient,
    RoverClient,
    RoverHistoryClient,
    BatteryClient,
    DataLogger,
    Utils,
    BaseClient, # Imported for type hinting in callbacks
)
from renogybt.ConfigManager import ConfigManager
from renogybt.exceptions import (
    DeviceNotFoundError,
    ConnectionError,
    ReadTimeoutError,
    InvalidResponseError,
    ConfigError, # Though ConfigManager raises ValueError, good for completeness
    RenogyBTError,
)
from renogybt.datamodels import RoverData, BatteryData # Import specific dataclasses
from renogybt import constants as C


# Determine configuration file path
config_file_arg = sys.argv[1] if len(sys.argv) > 1 else "config.ini"
# Ensure config_path is absolute or relative to the script's directory for robustness
config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), config_file_arg)

# Initialize ConfigManager and handle potential early errors
# A temporary logger is set up for errors occurring before full log config.
try:
    config_manager = ConfigManager(config_file=config_path)
except FileNotFoundError:
    logging.basicConfig(
        level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.error(
        f"Configuration file '{config_path}' not found. Please ensure it exists."
    )
    sys.exit(1)
except ValueError as e:  # ConfigManager's _validate_config raises ValueError for missing items
    logging.basicConfig(
        level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.error(f"Configuration error in '{config_path}': {e}")
    sys.exit(1)
except Exception as e:  # Catch any other unexpected error during config loading
    logging.basicConfig(
        level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.error(f"Unexpected error loading configuration from '{config_path}': {e}", exc_info=True)
    sys.exit(1)

# Configure logging based on settings from config_manager
# Default to INFO if not specified or if the value is invalid.
log_level_str = config_manager.get(
    C.CONFIG_SECTION_DATA, C.CONFIG_KEY_LOG_LEVEL, fallback="INFO"
).upper()
# Attempt to get the numeric log level from the logging module
numeric_log_level = getattr(logging, log_level_str, None)
if not isinstance(numeric_log_level, int):
    numeric_log_level = logging.INFO # Default to INFO if parsing failed
    logging.warning(f"Invalid log level '{log_level_str}' in config. Defaulting to INFO.")

logging.basicConfig(
    level=numeric_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Now that logging is configured, get a logger for this script
logger = logging.getLogger(__name__)

logger.info(f"Script started. Log level set to {logging.getLevelName(numeric_log_level)}.")
logger.info(f"Using configuration file: {config_path}")

# Initialize DataLogger
data_logger: DataLogger = DataLogger(config_manager)


def on_data_received(client: BaseClient, data_obj: Union[RoverData, BatteryData, dict, Any]) -> None:
    """
    Callback function invoked when data is received from the Renogy device.

    This function processes the received data, which can be a dataclass instance
    (for device status reads) or a dictionary (for responses to write operations).
    It logs the data, filters it based on configuration, and sends it to
    configured external logging services (remote HTTP, MQTT, PVOutput).

    Args:
        client: The client instance that received the data.
        data_obj: The received data object. This can be a `RoverData`,
                  `BatteryData` instance, or a simple dictionary for
                  responses to write commands.
    """
    # Convert dataclass to dict for consistent processing by filter_fields and loggers
    log_data_dict: dict
    if dataclasses.is_dataclass(data_obj):
        log_data_dict = dataclasses.asdict(data_obj)
        logger.debug(f"Received dataclass object of type {type(data_obj).__name__}, converted to dict.")
    elif isinstance(data_obj, dict):
        log_data_dict = data_obj
        logger.debug("Received dictionary object (likely a write response).")
    else:
        logger.warning(f"Received data of unexpected type: {type(data_obj)}. Raw data: {str(data_obj)[:200]}")
        log_data_dict = {"raw_data": str(data_obj)} # Fallback for logging

    # Apply field filtering from config.ini ([data] fields = ...), if specified
    fields_to_log_str = config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_FIELDS)
    if fields_to_log_str: # If a fields string is defined
        # Utils.filter_fields expects a dict and a comma-separated string of keys
        final_log_data = Utils.filter_fields(log_data_dict, fields_to_log_str)
        logger.debug(f"Applied field filtering. Fields: '{fields_to_log_str}'. Filtered data: {final_log_data}")
    else: # No specific fields requested, log all available data from the dict
        final_log_data = log_data_dict
        logger.debug("No field filtering applied, logging all available data.")

    # Determine device name for log message (preferring metadata if available)
    device_name_for_log = final_log_data.get(
        C.META_DEVICE_ALIAS, # Check for __device metadata first
        client.device_alias if client else "UnknownDevice" # Fallback to client's alias
    )
    logger.info(f"Data from '{device_name_for_log}': {final_log_data}")

    # Log to external services if enabled in config
    if config_manager.get(C.CONFIG_SECTION_REMOTE_LOGGING, C.CONFIG_KEY_RL_ENABLED, fallback="false").lower() == "true":
        data_logger.log_remote(json_data=final_log_data)
    if config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_ENABLED, fallback="false").lower() == "true":
        data_logger.log_mqtt(json_data=final_log_data)

    # PVOutput logging is specific to RoverData and requires certain fields
    if (
        config_manager.get(C.CONFIG_SECTION_PVOUTPUT, C.CONFIG_KEY_PV_ENABLED, fallback="false").lower() == "true"
        and config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_TYPE) == C.DEVICE_TYPE_ROVER
        and isinstance(data_obj, RoverData) # Ensure it's the RoverData dataclass for direct attribute access
    ):
        logger.debug("Attempting to log to PVOutput with RoverData.")
        # Construct payload using direct attribute access from the original RoverData object
        # to ensure type safety and access to all necessary fields, regardless of filtering.
        pv_output_payload = {
            C.KEY_PVOUTPUT_POWER_GENERATION_TODAY: data_obj.power_generation_today,
            C.KEY_PVOUTPUT_PV_POWER: data_obj.pv_power,
            C.KEY_PVOUTPUT_POWER_CONSUMPTION_TODAY: data_obj.power_consumption_today,
            C.KEY_PVOUTPUT_LOAD_POWER: data_obj.load_power,
            C.KEY_PVOUTPUT_CONTROLLER_TEMP: data_obj.controller_temperature,
            C.KEY_PVOUTPUT_BATTERY_VOLTAGE: data_obj.battery_voltage,
        }
        # Check if all required fields for PVOutput are present and not None
        required_pvoutput_keys = [
            C.KEY_PVOUTPUT_POWER_GENERATION_TODAY, C.KEY_PVOUTPUT_PV_POWER,
            C.KEY_PVOUTPUT_POWER_CONSUMPTION_TODAY, C.KEY_PVOUTPUT_LOAD_POWER,
            C.KEY_PVOUTPUT_CONTROLLER_TEMP, C.KEY_PVOUTPUT_BATTERY_VOLTAGE,
        ]
        if all(pv_output_payload.get(key) is not None for key in required_pvoutput_keys):
            data_logger.log_pvoutput(json_data=pv_output_payload)
        else:
            logger.warning(
                "Skipping PVOutput logging for RoverData due to missing essential data fields. "
                f"Required: {required_pvoutput_keys}, Available in original data_obj: {vars(data_obj)}"
            )

    # Stop client if polling is not enabled (i.e., run once mode)
    if not config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING, fallback="true").lower() == "true":
        logger.info("Polling is disabled. Stopping client after one data cycle.")
        client.stop()


def on_error(client: BaseClient, error: Union[Exception, str]) -> None:
    """
    Callback function invoked when an error occurs in the client.

    Logs the error with appropriate details based on the error type.

    Args:
        client: The client instance that encountered the error.
        error: The exception object or error message string.
    """
    device_alias = client.device_alias if client else "UnknownClient"
    if isinstance(error, DeviceNotFoundError):
        logger.error(
            f"Device Discovery Error for '{device_alias}': {error}. "
            "Ensure device is powered, in range, and MAC/alias in config is correct."
        )
    elif isinstance(error, ConnectionError):
        logger.error(
            f"Connection Error for '{device_alias}': {error}. "
            "Check Bluetooth connectivity and device status. Retries may have been exhausted."
        )
    elif isinstance(error, ReadTimeoutError):
        logger.error(
            f"Read Timeout for '{device_alias}': {error}. Device did not respond in time."
        )
    elif isinstance(error, InvalidResponseError):
        logger.error(
            f"Invalid Response from '{device_alias}': {error}. Device sent unexpected data."
        )
    elif isinstance(error, ConfigError): # Currently ConfigManager raises ValueError
        logger.error(f"Configuration Issue for '{device_alias}': {error}.")
    elif isinstance(error, RenogyBTError): # Catch-all for other library-specific errors
        logger.error(f"A RenogyBT library error occurred for '{device_alias}': {error}", exc_info=True)
    elif isinstance(error, Exception): # General exceptions
        logger.error(f"An unexpected error occurred in client for '{device_alias}': {error}", exc_info=True)
    else: # Simple string messages (less common now)
        logger.error(f"An error occurred in client for '{device_alias}': {error}")


# --- Main script execution ---
logger.info("Initializing Renogy BT client...")
try:
    device_type_from_config = config_manager.get(
        C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_TYPE
    )
    client_instance: Optional[BaseClient] = None # For type hinting
    logger.debug(f"Device type specified in configuration: '{device_type_from_config}'")

    if device_type_from_config == C.DEVICE_TYPE_ROVER:
        client_instance = RoverClient(config_manager, on_data_received, on_error)
    elif device_type_from_config == C.DEVICE_TYPE_ROVER_HISTORY:
        client_instance = RoverHistoryClient(config_manager, on_data_received, on_error) # Assuming this client exists
    elif device_type_from_config == C.DEVICE_TYPE_BATTERY:
        client_instance = BatteryClient(config_manager, on_data_received, on_error)
    elif device_type_from_config == C.DEVICE_TYPE_INVERTER:
        client_instance = InverterClient(config_manager, on_data_received, on_error) # Assuming this client exists
    elif device_type_from_config == C.DEVICE_TYPE_DCCHARGER:
        client_instance = DCChargerClient(config_manager, on_data_received, on_error) # Assuming this client exists
    else:
        logger.error(
            f"Unknown device type '{device_type_from_config}' in configuration. Cannot start client."
        )
        sys.exit(1)

    logger.info(f"Starting client for device type: '{device_type_from_config}'...")
    if client_instance:
        client_instance.start()
    logger.info("Client execution finished or was stopped by user/error.")

except RenogyBTError as e: # Errors propagated from client.start()
    logger.critical(
        f"Client execution failed due to RenogyBTError: {e.__class__.__name__}: {e}. "
        "Check logs above for details from on_error callback.", exc_info=True
    )
    sys.exit(1)
except KeyboardInterrupt:
    logger.info("Application terminated by user (KeyboardInterrupt).")
    # Client's stop method should handle cleanup if it was started and if loop allows.
    sys.exit(0)
except Exception as e: # Catch-all for any other unexpected critical errors in example.py
    logger.critical(
        f"An unexpected critical error occurred in example.py execution: {e}", exc_info=True
    )
    sys.exit(1)
