# -*- coding: utf-8 -*-
"""
renogybt.BatteryClient
~~~~~~~~~~~~~~~~~~~~~~

This module provides the `BatteryClient` class, a specific implementation of
`BaseClient` for interacting with Renogy smart lithium batteries that support
Bluetooth communication (e.g., via a BT-2 module or built-in).

It defines the data sections relevant to these batteries, such as cell voltages,
temperatures, overall battery status (voltage, current, capacity), and device
information. The parsed data is stored in a `BatteryData` dataclass instance.
"""
import logging
from .BaseClient import BaseClient
from .Utils import bytes_to_int, format_temperature
from .datamodels import BatteryData
from . import constants as C
from typing import Callable, Any, Optional # Keep one import


logger = logging.getLogger(__name__)

# Device-specific mapping for function codes to readable strings
FUNCTION_MAP = {
    C.OP_CODE_READ: "READ",
    C.OP_CODE_WRITE: "WRITE", # Though BatteryClient primarily reads
}


class BatteryClient(BaseClient):
    """
    Client for Renogy smart lithium batteries.

    Handles communication and data parsing for Renogy batteries equipped with
    Bluetooth. It defines data sections for polling cell information, temperatures,
    overall battery parameters, and device details.

    The `on_data_callback` will receive instances of `BatteryData`.

    Args:
        config_manager (ConfigManager): Configuration manager instance.
        on_data_callback (Callable[[BaseClient, BatteryData], None], optional):
            Async callback invoked when new data is available.
            Receives the client instance and a `BatteryData` object.
        on_error_callback (Callable[[BaseClient, Exception], None], optional):
            Callback invoked when an error occurs.
            Receives the client instance and the exception object.
    """
    def __init__(
        self,
        config_manager,
        on_data_callback: Optional[Callable[[Any, BatteryData], None]] = None,
        on_error_callback: Optional[Callable[[Any, Exception], None]] = None
    ):
        super().__init__(config_manager)
        self.on_data_callback = on_data_callback
        self.on_error_callback = on_error_callback

        # Define data sections for Battery: register address, number of words, parser method
        self.sections = [
            { # Cell voltages (typically up to 16 cells for many models)
                C.KEY_REGISTER: 5000, # Example starting register for cell voltages
                C.KEY_WORDS: 17,      # Max cells (e.g. 16) + cell count word
                C.KEY_PARSER: self.parse_cell_volt_info,
            },
            { # Cell temperatures (typically fewer sensors than cells)
                C.KEY_REGISTER: 5017, # Example starting register for cell temperatures
                C.KEY_WORDS: 17,      # Max sensors (e.g. 16) + sensor count word
                C.KEY_PARSER: self.parse_cell_temp_info,
            },
            { # Overall battery information
                C.KEY_REGISTER: 5042, # Example starting register for battery status
                C.KEY_WORDS: 6,       # Current, Voltage, Remaining Charge, Capacity
                C.KEY_PARSER: self.parse_battery_info,
            },
            { # Device Info (Model)
                C.KEY_REGISTER: 5122, # Example register for device info
                C.KEY_WORDS: 8,       # Typically 16 bytes for model string
                C.KEY_PARSER: self.parse_device_info,
            },
            { # Device Address (Modbus ID from device)
                C.KEY_REGISTER: 5223, # Example register for device address
                C.KEY_WORDS: 1,
                C.KEY_PARSER: self.parse_device_address,
            },
        ]
        logger.debug(f"BatteryClient initialized for '{self.device_alias}'. Sections defined: {len(self.sections)}")


    def _get_empty_data_container(self) -> BatteryData:
        """
        Returns a new, empty `BatteryData` instance.
        Overrides `BaseClient._get_empty_data_container`.
        """
        logger.debug(
            f"BatteryClient._get_empty_data_container() called for '{self.device_alias}'"
        )
        return BatteryData()

    def parse_cell_volt_info(self, bs: bytearray) -> None:
        """Parses individual cell voltage data from response bytes."""
        logger.debug(f"Parsing cell voltage info for '{self.device_alias}'...")
        assert isinstance(self.data, BatteryData), (
            f"self.data is not BatteryData instance in parse_cell_volt_info, it is {type(self.data)}"
        )
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        # Cell count should be an integer for range()
        self.data.cell_count = int(bytes_to_int(bs, 3, 2))

        if self.data.cell_count is not None and 0 < self.data.cell_count <= 16:
            self.data.cell_voltages.clear()
            for i in range(0, self.data.cell_count): # cell_count is now int
                voltage = bytes_to_int(bs, 5 + i * 2, 2, scale=0.001)
                self.data.cell_voltages[i+1] = voltage # Store with 1-based indexing for cells
            logger.debug(
                f"Cell voltage info parsed for '{self.device_alias}': Count={self.data.cell_count}, Voltages={self.data.cell_voltages}"
            )
        elif self.data.cell_count is not None: # Unusual cell count
             logger.warning(f"Unexpected cell count ({self.data.cell_count}) received for '{self.device_alias}'. Max 16 expected.")
        else:
            logger.warning(f"Could not parse cell count for '{self.device_alias}'.")


    def parse_cell_temp_info(self, bs: bytearray) -> None:
        """Parses individual cell/sensor temperature data from response bytes."""
        logger.debug(f"Parsing cell temperature info for '{self.device_alias}'...")
        assert isinstance(self.data, BatteryData), (
            f"self.data is not BatteryData instance in parse_cell_temp_info, it is {type(self.data)}"
        )
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        # Sensor count should be an integer
        self.data.sensor_count = int(bytes_to_int(bs, 3, 2))

        if self.data.sensor_count is not None and 0 < self.data.sensor_count <= 16:
            self.data.temperatures.clear()
            temp_unit = self.config_manager.get(
                C.CONFIG_SECTION_DATA, C.CONFIG_KEY_TEMP_UNIT
            )
            for i in range(0, self.data.sensor_count): # sensor_count is now int
                raw_temp = bytes_to_int(bs, 5 + i * 2, 2, signed=True, scale=0.1)
                self.data.temperatures[i+1] = format_temperature(raw_temp, temp_unit)
            logger.debug(
                f"Cell temperature info parsed for '{self.device_alias}': Count={self.data.sensor_count}, Temps={self.data.temperatures}"
            )
        elif self.data.sensor_count is not None:
            logger.warning(f"Unexpected temperature sensor count ({self.data.sensor_count}) for '{self.device_alias}'. Max 16 expected.")
        else:
            logger.warning(f"Could not parse temperature sensor count for '{self.device_alias}'.")


    def parse_battery_info(self, bs: bytearray) -> None:
        """Parses overall battery status information (voltage, current, capacity)."""
        logger.debug(f"Parsing battery info for '{self.device_alias}'...")
        assert isinstance(self.data, BatteryData), (
            f"self.data is not BatteryData instance in parse_battery_info, it is {type(self.data)}"
        )
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        self.data.current = bytes_to_int(bs, 3, 2, signed=True, scale=0.01) # Amps
        self.data.voltage = bytes_to_int(bs, 5, 2, scale=0.1)  # Volts
        self.data.remaining_charge = bytes_to_int(bs, 7, 4, scale=0.001) # Amp-hours (Ah)
        self.data.capacity = bytes_to_int(bs, 11, 4, scale=0.001) # Total capacity (Ah)
        logger.debug(
            f"Battery info parsed for '{self.device_alias}': Voltage={self.data.voltage:.2f}V, Current={self.data.current:.2f}A, "
            f"Remaining={self.data.remaining_charge:.3f}Ah, Capacity={self.data.capacity:.3f}Ah"
        )

    def parse_device_info(self, response_bytes: bytearray) -> None:
        """Parses device model information."""
        logger.debug(f"Parsing device info for '{self.device_alias}'...")
        assert isinstance(self.data, BatteryData), (
            f"self.data is not BatteryData instance in parse_device_info, it is {type(self.data)}"
        )
        self.data.function = FUNCTION_MAP.get(bytes_to_int(response_bytes, 1, 1))
        # Model string for batteries might have null termination.
        super()._parse_device_info(
            response_bytes, model_start_index=3, model_end_index=19, strip_chars="\x00"
        )
        logger.debug(
            f"Device info parsed for '{self.device_alias}': Model='{self.data.model}'"
        )

    def parse_device_address(self, response_bytes: bytearray) -> None:
        """Parses the device's Modbus ID."""
        logger.debug(f"Parsing device address for '{self.device_alias}'...")
        assert isinstance(self.data, BatteryData), (
            f"self.data is not BatteryData instance in parse_device_address, it is {type(self.data)}"
        )
        # Device ID for batteries is often 2 bytes at offset 3.
        super()._parse_device_address(
            response_bytes, address_start_index=3, address_length_bytes=2
        )
        logger.debug(
            f"Device address parsed for '{self.device_alias}': DeviceID='{self.data.device_id}'"
        )
