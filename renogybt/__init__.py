"""
Renogy BT/BLE Client Library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Python library for interacting with Renogy devices over Bluetooth Low Energy.

Provides client implementations for various Renogy devices like Rover solar charge
controllers, smart batteries, inverters, and DC-DC chargers. Includes utilities
for data parsing, BLE communication management, and data logging.

Example usage:

    from renogybt import RoverClient, ConfigManager

    # Load configuration
    config_manager = ConfigManager(config_file='config.ini')

    # Define callbacks
    def on_data(client, data):
        print(f"Received from {data.get('__device', 'Unknown')}: {data}")

    def on_error(client, error):
        print(f"Error: {error}")

    # Initialize and start client
    client = RoverClient(config_manager, on_data_callback=on_data, on_error_callback=on_error)
    client.start()

Available Modules:
- BaseClient: Base class for all device clients.
- RoverClient: Client for Rover charge controllers.
- BatteryClient: Client for Renogy smart batteries.
- InverterClient: Client for Renogy inverters.
- DCChargerClient: Client for Renogy DC-DC chargers.
- RoverHistoryClient: Client for Rover historical data.
- DataLogger: Utility for logging data to various outputs (remote, MQTT, PVOutput).
- ConfigManager: Handles loading and validation of `config.ini`.
- BLEManager: Manages Bluetooth Low Energy connections and communication.
- Utils: Helper functions for data conversion and parsing.
- constants: Defines shared constants used across the library.
- datamodels: Contains dataclasses for structured device data.
- exceptions: Custom exception classes for the library.
"""

from .RoverClient import RoverClient
from .DataLogger import DataLogger
from .BatteryClient import BatteryClient
from .RoverHistoryClient import RoverHistoryClient
from .InverterClient import InverterClient
from .DCChargerClient import DCChargerClient
from .ConfigManager import ConfigManager # Added ConfigManager
from .BaseClient import BaseClient # Potentially useful for type hinting or extending
# Utils is typically not part of the public API surface via __all__ unless specific functions are promoted.
# For now, keeping it as a star import as per original, but not including in __all__.
from .Utils import *

__all__ = [
    'RoverClient',
    'DataLogger',
    'BatteryClient',
    'RoverHistoryClient',
    'InverterClient',
    'DCChargerClient',
    'ConfigManager',
    'BaseClient',
    # Specific client data models can be added if they are commonly used for type checking by users
    # e.g., 'RoverData', 'BatteryData' from .datamodels
    # For now, keeping __all__ focused on primary interface classes.
]

__version__ = "0.1.0" # Example version
