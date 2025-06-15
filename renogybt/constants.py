# Bluetooth Service and Characteristic UUIDs
UUID_WRITE_SERVICE = "0000ffd0-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY_CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"
UUID_WRITE_CHAR = "0000ffd1-0000-1000-8000-00805f9b34fb"

# Operation Codes
OP_CODE_READ = 3
OP_CODE_WRITE = 6
OP_CODE_READ_SUCCESS = 3 # Response code for successful read
OP_CODE_READ_ERROR = 131 # Response code for read error

# Timeouts
DEFAULT_READ_TIMEOUT_S = 15

# Section Definition Keys
KEY_REGISTER = 'register'
KEY_WORDS = 'words'
KEY_PARSER = 'parser'

# Common Data Keys (used in self.data dicts before dataclasses, and potentially in simple dict responses)
# For dataclasses, prefer direct attribute access.
KEY_FUNCTION = 'function' # e.g. "READ" or "WRITE" based on op code
KEY_DEVICE_ID = 'device_id' # Device ID read from device, not from config
KEY_MODEL = 'model'

# Metadata Keys (added by BaseClient to the data object sent to callback)
META_DEVICE_ALIAS = '__device' # Value is the device alias from config
META_CLIENT_NAME = '__client' # Value is the client class name

# Configuration Sections and Keys
# ConfigManager sections
CONFIG_SECTION_DEVICE = 'device'
CONFIG_SECTION_DATA = 'data'
CONFIG_SECTION_REMOTE_LOGGING = 'remote_logging'
CONFIG_SECTION_MQTT = 'mqtt'
CONFIG_SECTION_PVOUTPUT = 'pvoutput'

# Keys for CONFIG_SECTION_DEVICE
CONFIG_KEY_MAC_ADDR = 'mac_addr'
CONFIG_KEY_ALIAS = 'alias'
CONFIG_KEY_TYPE = 'type'
CONFIG_KEY_DEVICE_ID = 'device_id' # Device ID from config file
CONFIG_KEY_CONNECT_RETRIES = 'connect_retries'
CONFIG_KEY_CONNECT_RETRY_DELAY = 'connect_retry_delay'

# Keys for CONFIG_SECTION_DATA
CONFIG_KEY_ENABLE_POLLING = 'enable_polling'
CONFIG_KEY_POLL_INTERVAL = 'poll_interval'
CONFIG_KEY_FIELDS = 'fields' # For filtering output
CONFIG_KEY_TEMP_UNIT = 'temperature_unit'
CONFIG_KEY_LOG_LEVEL = 'log_level' # Added

# Keys for CONFIG_SECTION_REMOTE_LOGGING
CONFIG_KEY_RL_ENABLED = 'enabled'
CONFIG_KEY_RL_URL = 'url'
CONFIG_KEY_RL_AUTH_HEADER = 'auth_header'

# Keys for CONFIG_SECTION_MQTT
CONFIG_KEY_MQTT_ENABLED = 'enabled'
CONFIG_KEY_MQTT_SERVER = 'server'
CONFIG_KEY_MQTT_PORT = 'port'
CONFIG_KEY_MQTT_TOPIC = 'topic'
CONFIG_KEY_MQTT_USER = 'user'
CONFIG_KEY_MQTT_PASSWORD = 'password'

# Keys for CONFIG_SECTION_PVOUTPUT
CONFIG_KEY_PV_ENABLED = 'enabled'
CONFIG_KEY_PV_API_KEY = 'api_key'
CONFIG_KEY_PV_SYSTEM_ID = 'system_id'


# RoverClient specific value mappings (can be client-specific or moved here if truly global)
# FUNCTION_MAP = {
#     OP_CODE_READ: "READ",
#     OP_CODE_WRITE: "WRITE",
# }
# Using OP_CODE_READ/WRITE directly is often clearer than another mapping.

# Example of how client-specific status maps could be handled if desired:
# ROVER_CHARGING_STATE_MAP = {
#     0: 'deactivated', 1: 'activated', 2: 'mppt', 3: 'equalizing',
#     4: 'boost', 5: 'floating', 6: 'current limiting'
# }
# ROVER_LOAD_STATE_MAP = {0: 'off', 1: 'on'}
# ROVER_BATTERY_TYPE_MAP = {1: 'open', 2: 'sealed', 3: 'gel', 4: 'lithium', 5: 'custom'}

# For now, keeping client-specific status maps (CHARGING_STATE, etc.) in their respective client files
# as they are not shared across all clients. If a new client uses the exact same map, then consider moving.

# Device type strings used in config and example.py
DEVICE_TYPE_ROVER = 'RNG_CTRL'
DEVICE_TYPE_ROVER_HISTORY = 'RNG_CTRL_HIST'
DEVICE_TYPE_BATTERY = 'RNG_BATT'
DEVICE_TYPE_INVERTER = 'RNG_INVT'
DEVICE_TYPE_DCCHARGER = 'RNG_DCC'

# ALIAS_PREFIXES used in BaseClient for device discovery logging
DEVICE_ALIAS_PREFIXES = ['BT-TH', 'RNGRBP', 'BTRIC']

# PVOutput Data Keys (as used in example.py, corresponding to RoverData fields)
# These are the keys expected by the log_pvoutput function in DataLogger,
# when data is constructed from RoverData in example.py.
KEY_PVOUTPUT_POWER_GENERATION_TODAY = 'power_generation_today'
KEY_PVOUTPUT_PV_POWER = 'pv_power'
KEY_PVOUTPUT_POWER_CONSUMPTION_TODAY = 'power_consumption_today'
KEY_PVOUTPUT_LOAD_POWER = 'load_power'
KEY_PVOUTPUT_CONTROLLER_TEMP = 'controller_temperature'
KEY_PVOUTPUT_BATTERY_VOLTAGE = 'battery_voltage'
