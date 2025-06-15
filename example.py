import logging
import os
import sys
from renogybt import (
    DCChargerClient, InverterClient, RoverClient, RoverHistoryClient, BatteryClient,
    DataLogger, Utils
)
from renogybt.ConfigManager import ConfigManager
from renogybt.exceptions import DeviceNotFoundError, ConnectionError, ReadTimeoutError, InvalidResponseError, ConfigError, RenogyBTError
from renogybt.datamodels import RoverData, BatteryData
from renogybt import constants as C # Import constants
import dataclasses

# Logger will be configured after reading config
# logging.basicConfig(level=logging.INFO) # Remove initial basicConfig

config_file = sys.argv[1] if len(sys.argv) > 1 else 'config.ini'
# Ensure config_path is absolute or relative to the script's directory
config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), config_file)

config_manager = None # Initialize to None
try:
    config_manager = ConfigManager(config_file=config_path)
except FileNotFoundError:
    # Use a temporary basicConfig for pre-config manager errors
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error(f"Configuration file '{config_path}' not found. Please ensure it exists.")
    sys.exit(1)
except ValueError as e: # ConfigManager's _validate_config raises ValueError
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error(f"Configuration error: {e}")
    sys.exit(1)
except Exception as e: # Catch any other unexpected error during config loading
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error(f"Unexpected error loading configuration: {e}")
    sys.exit(1)

# Configure logging based on settings from config_manager
log_level_str = config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_LOG_LEVEL, fallback='INFO').upper()
numeric_log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=numeric_log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__) # Logger for example.py itself

logger.info(f"Script started. Log level set to {log_level_str}.")

data_logger: DataLogger = DataLogger(config_manager)

# the callback func when you receive data
def on_data_received(client, data_obj):

    # The data_obj could be a dataclass instance (RoverData, BatteryData) or a dict (for write responses)
    # Utils.filter_fields likely expects a dict.
    # For dataclasses, we might want to log all fields or convert to dict first.

    log_data = {}
    is_dataclass_instance = dataclasses.is_dataclass(data_obj)

    if is_dataclass_instance:
        log_data = dataclasses.asdict(data_obj)
    elif isinstance(data_obj, dict): # For simple dict responses (e.g., from write operations)
        log_data = data_obj
    else:
        logging.warning(f"Received data of unexpected type: {type(data_obj)}")
        log_data = {"raw_data": str(data_obj)}

    # Apply filtering if fields are specified and data is suitable for filtering
    # If fields are defined, it implies user wants specific data.
    # If it's a simple dict response from a write op, filtering might not apply or desired.
    fields_to_log = config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_FIELDS)
    if fields_to_log:
        # Ensure log_data is a dict before filtering.
        # Utils.filter_fields should ideally handle non-existing keys gracefully.
        if not isinstance(log_data, dict):
             logging.warning("Cannot apply field filtering to non-dictionary data. Logging all available data.")
             # Fallback to logging whatever log_data is, or skip filtering.
             # For now, let's assume filter_fields can take it or we log the raw dict.
             pass # Keep log_data as is. filter_fields might fail or do its best.

        # If it's a dataclass, __device and __client were added by BaseClient.
        # If it's a dict, they might or might not be there.
        # Let filter_fields handle it.
        filtered_log_data = Utils.filter_fields(log_data, fields_to_log)
    else:
        filtered_log_data = log_data # Log all fields if no filter specified

    # Add __device and __client for logging if not already present by filter_fields
    # These are added by BaseClient.on_read_operation_complete to the dataclass/dict
    # So they should be in log_data if it came from a full read cycle.
    # For simple write responses, they won't be there.
    device_name_for_log = log_data.get(C.META_DEVICE_ALIAS, client.ble_manager.device.name if client.ble_manager and client.ble_manager.device else "UnknownDevice")

    logger.info(f"Data received from {device_name_for_log}: {filtered_log_data}")

    # For external logging services, send the filtered_log_data
    if config_manager.get(C.CONFIG_SECTION_REMOTE_LOGGING, C.CONFIG_KEY_RL_ENABLED).lower() == 'true':
        data_logger.log_remote(json_data=filtered_log_data)
    if config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_ENABLED).lower() == 'true':
        data_logger.log_mqtt(json_data=filtered_log_data)

    # PVOutput logging needs specific fields. We need to ensure they exist in filtered_log_data.
    # This part is specific to RoverData.
    if config_manager.get(C.CONFIG_SECTION_PVOUTPUT, C.CONFIG_KEY_PV_ENABLED).lower() == 'true' and \
       config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_TYPE) == C.DEVICE_TYPE_ROVER and \
       isinstance(data_obj, RoverData): # Ensure it's RoverData for these fields
        # Construct a dict for pvoutput from the RoverData instance or filtered_log_data
        # Using direct attribute access for clarity and type safety with dataclasses
        pv_output_payload = {
            C.KEY_PVOUTPUT_POWER_GENERATION_TODAY: data_obj.power_generation_today,
            C.KEY_PVOUTPUT_PV_POWER: data_obj.pv_power,
            C.KEY_PVOUTPUT_POWER_CONSUMPTION_TODAY: data_obj.power_consumption_today,
            C.KEY_PVOUTPUT_LOAD_POWER: data_obj.load_power,
            C.KEY_PVOUTPUT_CONTROLLER_TEMP: data_obj.controller_temperature,
            C.KEY_PVOUTPUT_BATTERY_VOLTAGE: data_obj.battery_voltage
        }
        # Ensure all keys for pvoutput are present before sending
        # These keys should be defined in constants.py if they become standard PVOutput keys
        required_pvoutput_keys = [
            C.KEY_PVOUTPUT_POWER_GENERATION_TODAY, C.KEY_PVOUTPUT_PV_POWER,
            C.KEY_PVOUTPUT_POWER_CONSUMPTION_TODAY, C.KEY_PVOUTPUT_LOAD_POWER,
            C.KEY_PVOUTPUT_CONTROLLER_TEMP, C.KEY_PVOUTPUT_BATTERY_VOLTAGE
        ]
        if all(pv_output_payload.get(key) is not None for key in required_pvoutput_keys):
            data_logger.log_pvoutput(json_data=pv_output_payload)
        else:
            logging.warning("Skipping PVOutput logging due to missing data fields in RoverData.")

    if not config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING).lower() == 'true':
        client.stop()

# error callback
def on_error(client, error):
    # isinstance check allows handling of both Exception objects and simple string messages
    if isinstance(error, DeviceNotFoundError):
        logging.error(f"Device Discovery Error: {error}. Ensure the device is powered on, in range, and MAC address is correct in config.")
    elif isinstance(error, ConnectionError):
        logging.error(f"Connection Error: {error}. Check Bluetooth connectivity and device status. Retries may have been exhausted.")
    elif isinstance(error, ReadTimeoutError):
        logging.error(f"Read Timeout: {error}. The device did not respond in time. Check connections or device load.")
    elif isinstance(error, InvalidResponseError):
        logging.error(f"Invalid Response: {error}. The device sent unexpected data. Firmware mismatch or interference?")
    elif isinstance(error, ConfigError): # Though ConfigManager currently raises ValueError
        logging.error(f"Configuration Issue: {error}.")
    elif isinstance(error, RenogyBTError): # Catch-all for other library-specific errors
        logging.error(f"A RenogyBT library error occurred: {error}")
    elif isinstance(error, Exception): # General exceptions passed through
        logging.error(f"An unexpected error occurred in the client: {error}")
    else: # Simple string messages
        logging.error(f"An error occurred in the client: {error}")
    # Depending on the error, you might want to add specific logic here,
    # e.g., sys.exit(1) for critical errors that prevent continuation.
    # For now, just logging and letting the client's stop/future handling manage exit.

# start client
logger.info("Initializing client...")
try:
    device_type_from_config = config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_TYPE)
    client_instance = None
    logger.debug(f"Device type from config: {device_type_from_config}")

    if device_type_from_config == C.DEVICE_TYPE_ROVER:
        client_instance = RoverClient(config_manager, on_data_received, on_error)
    elif device_type_from_config == C.DEVICE_TYPE_ROVER_HISTORY:
        client_instance = RoverHistoryClient(config_manager, on_data_received, on_error)
    elif device_type_from_config == C.DEVICE_TYPE_BATTERY:
        client_instance = BatteryClient(config_manager, on_data_received, on_error)
    elif device_type_from_config == C.DEVICE_TYPE_INVERTER:
        client_instance = InverterClient(config_manager, on_data_received, on_error)
    elif device_type_from_config == C.DEVICE_TYPE_DCCHARGER:
        client_instance = DCChargerClient(config_manager, on_data_received, on_error)
    else:
        logger.error(f"Unknown device type '{device_type_from_config}' in configuration.")
        sys.exit(1)

    logger.info(f"Starting client for device type: {device_type_from_config}")
    if client_instance:
        client_instance.start() # This will run until future is set or an unhandled exception in start()
    logger.info("Client execution finished or was stopped.")

except RenogyBTError as e:
    logger.critical(f"Client execution failed: {e.__class__.__name__}: {e}. Check logs above for details from on_error callback.")
    sys.exit(1)
except KeyboardInterrupt:
    logger.info("Application terminated by user (KeyboardInterrupt).")
    sys.exit(0)
except Exception as e:
    logger.critical(f"An unexpected critical error occurred in example.py: {e}", exc_info=True)
    sys.exit(1)
