# -*- coding: utf-8 -*-
"""
renogybt.constants
~~~~~~~~~~~~~~~~~~

This module defines shared constants used throughout the Renogy BT/BLE client library.
These include Bluetooth UUIDs, operation codes, configuration keys, and other
fixed values to ensure consistency and avoid magic numbers/strings in the codebase.

Constants are grouped by their functional area.
"""

# Bluetooth Service and Characteristic UUIDs
# These are specific to the Renogy communication protocol.
UUID_WRITE_SERVICE = "0000ffd0-0000-1000-8000-00805f9b34fb"
"""Service UUID for writing commands."""
UUID_NOTIFY_CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"
"""Characteristic UUID for receiving notifications (data responses)."""
UUID_WRITE_CHAR = "0000ffd1-0000-1000-8000-00805f9b34fb"
"""Characteristic UUID for sending commands."""

# Operation Codes
# These codes define the type of MODBUS-like operations being performed.
OP_CODE_READ = 3
"""Operation code for read holding registers or similar read operations."""
OP_CODE_WRITE = 6
"""Operation code for write single register or similar write operations."""
OP_CODE_READ_SUCCESS = 3
"""Response code indicating a successful read operation.
   Note: This is often the same as OP_CODE_READ in Modbus-like protocols.
"""
OP_CODE_READ_ERROR = 131
"""Response code indicating an error during a read operation (Function code + 0x80).
   For example, 0x03 (Read) + 0x80 = 0x83 (131 decimal).
"""

# Timeouts
DEFAULT_READ_TIMEOUT_S = 15
"""Default timeout in seconds for waiting for a read operation to complete."""

# Section Definition Keys
# Used by BaseClient and its subclasses to define data sections for polling.
KEY_REGISTER = "register"
"""Dictionary key for the starting register of a data section."""
KEY_WORDS = "words"
"""Dictionary key for the number of words (2 bytes each) to read in a data section."""
KEY_PARSER = "parser"
"""Dictionary key for the parser method associated with a data section."""

# Common Data Keys
# These keys were used in `self.data` dictionaries before the introduction of dataclasses.
# They might still be used for simple dictionary responses (e.g., from write operations)
# or if direct attribute access on dataclasses is not suitable.
KEY_FUNCTION = "function"
"""Key for the operation function type (e.g., "READ", "WRITE")."""
KEY_DEVICE_ID = "device_id"
"""Key for the device ID, typically read from the device itself."""
KEY_MODEL = "model"
"""Key for the device model string."""

# Metadata Keys
# These keys are added by BaseClient to the data object (dict or dataclass)
# before it's passed to the user-defined callback.
META_DEVICE_ALIAS = "__device"
"""Metadata key for the device alias (from configuration)."""
META_CLIENT_NAME = "__client"
"""Metadata key for the client class name (e.g., "RoverClient")."""

# Configuration Sections and Keys
# These constants correspond to section and key names in the `config.ini` file.

# ConfigManager sections
CONFIG_SECTION_DEVICE = "device"
"""Top-level section for device-specific settings."""
CONFIG_SECTION_DATA = "data"
"""Top-level section for data handling and logging settings."""
CONFIG_SECTION_REMOTE_LOGGING = "remote_logging"
"""Section for remote HTTP logging settings."""
CONFIG_SECTION_MQTT = "mqtt"
"""Section for MQTT logging settings."""
CONFIG_SECTION_PVOUTPUT = "pvoutput"
"""Section for PVOutput.org logging settings."""

# Keys for CONFIG_SECTION_DEVICE
CONFIG_KEY_MAC_ADDR = "mac_addr"
CONFIG_KEY_ALIAS = "alias"
CONFIG_KEY_TYPE = "type"
CONFIG_KEY_DEVICE_ID = "device_id"  # Device ID from config file (Modbus ID)
CONFIG_KEY_CONNECT_RETRIES = "connect_retries"
CONFIG_KEY_CONNECT_RETRY_DELAY = "connect_retry_delay"

# Keys for CONFIG_SECTION_DATA
CONFIG_KEY_ENABLE_POLLING = "enable_polling"
CONFIG_KEY_POLL_INTERVAL = "poll_interval"
CONFIG_KEY_FIELDS = "fields"  # For filtering output fields
CONFIG_KEY_TEMP_UNIT = "temperature_unit" # Celsius (C) or Fahrenheit (F)
CONFIG_KEY_LOG_LEVEL = "log_level" # Logging level for the application (e.g., INFO, DEBUG)

# Keys for CONFIG_SECTION_REMOTE_LOGGING
CONFIG_KEY_RL_ENABLED = "enabled"
CONFIG_KEY_RL_URL = "url"
CONFIG_KEY_RL_AUTH_HEADER = "auth_header"

# Keys for CONFIG_SECTION_MQTT
CONFIG_KEY_MQTT_ENABLED = "enabled"
CONFIG_KEY_MQTT_SERVER = "server"
CONFIG_KEY_MQTT_PORT = "port"
CONFIG_KEY_MQTT_TOPIC = "topic"
CONFIG_KEY_MQTT_USER = "user"
CONFIG_KEY_MQTT_PASSWORD = "password"

# Keys for CONFIG_SECTION_PVOUTPUT
CONFIG_KEY_PV_ENABLED = "enabled"
CONFIG_KEY_PV_API_KEY = "api_key"
CONFIG_KEY_PV_SYSTEM_ID = "system_id"

# Device type strings used in config.ini `[device] type = ...` and example.py
DEVICE_TYPE_ROVER = "RNG_CTRL"
"""Device type identifier for Rover charge controllers."""
DEVICE_TYPE_ROVER_HISTORY = "RNG_CTRL_HIST" # Placeholder, actual value might differ
"""Device type identifier for Rover charge controller historical data."""
DEVICE_TYPE_BATTERY = "RNG_BATT"
"""Device type identifier for Renogy smart batteries."""
DEVICE_TYPE_INVERTER = "RNG_INVT" # Placeholder, actual value might differ
"""Device type identifier for Renogy inverters."""
DEVICE_TYPE_DCCHARGER = "RNG_DCC" # Placeholder, actual value might differ
"""Device type identifier for Renogy DC-DC chargers."""

# ALIAS_PREFIXES used in BaseClient for device discovery logging assistance
DEVICE_ALIAS_PREFIXES = ["BT-TH", "RNGRBP", "BTRIC"]
"""Common prefixes for Renogy Bluetooth device names."""

# PVOutput Data Keys (as used in example.py, corresponding to RoverData fields)
# These are the keys expected by the log_pvoutput function in DataLogger,
# when data is constructed from RoverData in example.py.
KEY_PVOUTPUT_POWER_GENERATION_TODAY = "power_generation_today"
KEY_PVOUTPUT_PV_POWER = "pv_power"
KEY_PVOUTPUT_POWER_CONSUMPTION_TODAY = "power_consumption_today"
KEY_PVOUTPUT_LOAD_POWER = "load_power"
KEY_PVOUTPUT_CONTROLLER_TEMP = "controller_temperature"
KEY_PVOUTPUT_BATTERY_VOLTAGE = "battery_voltage"
