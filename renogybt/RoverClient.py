# -*- coding: utf-8 -*-
"""
renogybt.RoverClient
~~~~~~~~~~~~~~~~~~~~

This module provides the `RoverClient` class, a specific implementation of
`BaseClient` for interacting with Renogy Rover series solar charge controllers
(and potentially compatible devices like Wanderer/Adventurer).

It defines the data sections to be read from the Rover, parsers for these
sections, and methods for device-specific commands like setting the load status.
The parsed data is stored in a `RoverData` dataclass instance.
"""
import logging
from .BaseClient import BaseClient
from .Utils import bytes_to_int, parse_temperature
from .datamodels import RoverData
from . import constants as C
import asyncio
from typing import Callable, Any, Optional # Added Optional for type hints

logger = logging.getLogger(__name__)

# Device-specific mappings for Rover status codes to human-readable strings.
# These are kept within the client as they are specific to this device type.
FUNCTION_MAP = {
    C.OP_CODE_READ: "READ",
    C.OP_CODE_WRITE: "WRITE",
}

CHARGING_STATE_MAP = {
    0: "deactivated",
    1: "activated", # Often indicates normal operation, but not a specific charging stage
    2: "mppt",      # Maximum Power Point Tracking (bulk charging)
    3: "equalizing",
    4: "boost",
    5: "floating",
    6: "current limiting", # Typically due to over-current or over-temperature
}

LOAD_STATE_MAP = {0: "off", 1: "on"}

BATTERY_TYPE_MAP = {
    1: "open",      # Open lead-acid
    2: "sealed",    # Sealed lead-acid
    3: "gel",       # Gel lead-acid
    4: "lithium",   # Lithium (typically LiFePO4)
    5: "custom"     # User-defined custom parameters
}


class RoverClient(BaseClient):
    """
    Client for Renogy Rover solar charge controllers.

    This class handles communication and data parsing for Rover series devices.
    It defines data sections for polling common Rover parameters like battery voltage,
    PV input, load status, and charging information. It also provides a method
    to control the load output.

    The `on_data_callback` will receive instances of `RoverData` for read operations
    and a simple dictionary for write operation responses (e.g., from `set_load`).

    Args:
        config_manager (ConfigManager): Configuration manager instance.
        on_data_callback (Callable[[BaseClient, Any], None], optional):
            Async callback invoked when new data is available.
            Receives the client instance and a `RoverData` object (for reads)
            or a dict (for write responses).
        on_error_callback (Callable[[BaseClient, Exception], None], optional):
            Callback invoked when an error occurs.
            Receives the client instance and the exception object.
    """
    def __init__(
        self,
        config_manager,
        on_data_callback: Optional[Callable[[Any, Any], None]] = None,
        on_error_callback: Optional[Callable[[Any, Exception], None]] = None
    ):
        super().__init__(config_manager)
        self.on_data_callback = on_data_callback
        self.on_error_callback = on_error_callback

        # Define data sections for Rover: register address, number of words, parser method
        self.sections = [
            {C.KEY_REGISTER: 12, C.KEY_WORDS: 8, C.KEY_PARSER: self.parse_device_info},
            {
                C.KEY_REGISTER: 26,
                C.KEY_WORDS: 1,
                C.KEY_PARSER: self.parse_device_address,
            },
            {
                C.KEY_REGISTER: 256, # Start of main data block for Rover
                C.KEY_WORDS: 34,     # Number of words to read for this block
                C.KEY_PARSER: self.parse_charging_info, # Method to parse this block
            },
            {
                C.KEY_REGISTER: 57348, # Register for battery type
                C.KEY_WORDS: 1,
                C.KEY_PARSER: self.parse_battery_type,
            },
        ]
        # Parameters for the "set load" command
        self.set_load_params = {C.KEY_FUNCTION: C.OP_CODE_WRITE, C.KEY_REGISTER: 0xE001} # Common register for load control on Rover

    async def on_data_received(self, response: bytearray) -> None:
        """
        Handles incoming data responses, routing write operation responses
        and delegating read responses to the base class.

        Args:
            response: The raw bytearray received from the device.
        """
        operation = bytes_to_int(response, 1, 1)
        if operation == C.OP_CODE_WRITE:
            logger.debug(f"Write operation response received by RoverClient for '{self.device_alias}'.")
            write_response_data = self.parse_set_load_response(response)
            self.on_write_operation_complete(write_response_data)
        else: # Assumed to be a read response or an error response for a read.
            if not isinstance(self.data, RoverData):
                logger.warning(
                    f"self.data in RoverClient for '{self.device_alias}' was not RoverData, re-initializing."
                )
                self.data = self._get_empty_data_container()
            await super().on_data_received(response)

    def on_write_operation_complete(self, write_data: dict) -> None:
        """
        Called when a write operation (e.g., set_load) receives a response.

        Invokes the `on_data_callback` with the specific response data from the
        write operation.

        Args:
            write_data: A dictionary containing the parsed response from the write command.
        """
        logger.info(
            f"Write operation complete for '{self.device_alias}'. Response data: {write_data}"
        )
        if self.on_data_callback is not None:
            self.on_data_callback(self, write_data)

    def _get_empty_data_container(self) -> RoverData:
        """
        Returns a new, empty `RoverData` instance.
        Overrides `BaseClient._get_empty_data_container`.
        """
        logger.debug(
            f"RoverClient._get_empty_data_container() called for '{self.device_alias}'"
        )
        return RoverData()

    def set_load(self, turn_on: bool) -> None:
        """
        Sets the load output on or off.

        Args:
            turn_on: True to turn the load on, False to turn it off.
        """
        value_to_write = 1 if turn_on else 0
        action = "ON" if turn_on else "OFF"
        logger.info(f"Setting load {action} for '{self.device_alias}' (Value: {value_to_write})")

        # Register 0xE001, Value 0x0100 for ON, 0x0000 for OFF (needs to be confirmed for specific Rover)
        # The value here seems to be directly 0 or 1 for some controllers.
        # The example used 'value' directly, which might mean 0x00 or 0x01 for the last word.
        # Let's assume the `create_generic_read_request` is for reading registers,
        # and a specific write request format might be needed if it's not just writing a single register.
        # For now, using the existing structure which implies writing to a register.
        # The register 266 (0x010A) was in the original set_load_params, this might be wrong for standard load control.
        # A common load control register is 0xE001.
        # If `self.set_load_params[C.KEY_REGISTER]` is 0xE001, then the value is typically 0x0100 (ON) or 0x0000 (OFF).
        # If the value is simply 0 or 1, it implies a different register or handling.
        # The original code used `value` (0 or 1) directly with register 266.
        # Let's stick to what was in `set_load_params` for register for now, but this may need review.
        # For register 0xE001, the value is typically 0x01 (ON) or 0x00 (OFF) for the *data byte*, not the word.
        # If the command writes a full word, it might be 0x0100 or 0x0000.
        # The original `self.create_generic_read_request` is misnamed if used for writes.
        # Assuming it's a generic "create_request_payload" for now.

        # Let's use the register from self.set_load_params (e.g. 0xE001)
        # and the value expected by that register (e.g. 0x0100 for ON, 0x0000 for OFF)
        # The `value` parameter to this function is boolean.
        # If register 0xE001: value should be 0x0100 for ON, 0x0000 for OFF.
        # If we use the old register 266, the value was 0 or 1.

        register_for_load = self.set_load_params[C.KEY_REGISTER]
        value_for_register = 0 # Default to OFF
        if register_for_load == 0xE001: # Common Renogy load control register
            value_for_register = 0x0100 if turn_on else 0x0000
        else: # Fallback or other register behavior (e.g. old 266)
            value_for_register = 1 if turn_on else 0


        request = self.create_generic_read_request( # Renamed in thought, but using existing method
            self.device_id_from_config,
            self.set_load_params[C.KEY_FUNCTION], # This should be C.OP_CODE_WRITE (6)
            register_for_load,
            value_for_register, # This is 'readWrd' / 'value' in create_generic_read_request
        )
        if request:
            logger.debug(f"Set load request payload for '{self.device_alias}': {request}")
            asyncio.create_task(self.ble_manager.characteristic_write_value(bytearray(request))) # Ensure bytearray
        else:
            logger.error(f"Failed to create set_load request for '{self.device_alias}'.")


    def parse_device_info(self, response_bytes: bytearray) -> None:
        """Parses device model information from response bytes."""
        logger.debug(f"Parsing device info for '{self.device_alias}'...")
        assert isinstance(self.data, RoverData), (
            f"self.data is not RoverData instance in parse_device_info, it is {type(self.data)}"
        )
        self.data.function = FUNCTION_MAP.get(bytes_to_int(response_bytes, 1, 1))
        # Model string is typically from byte 3 to 18 (16 bytes) for many Renogy devices.
        super()._parse_device_info(
            response_bytes, model_start_index=3, model_end_index=19
        ) # Default strip_chars is whitespace
        logger.debug(
            f"Device info parsed for '{self.device_alias}': Model='{self.data.model}'"
        )

    def parse_device_address(self, response_bytes: bytearray) -> None:
        """Parses the device's Modbus ID from response bytes."""
        logger.debug(f"Parsing device address for '{self.device_alias}'...")
        assert isinstance(self.data, RoverData), (
            f"self.data is not RoverData instance in parse_device_address, it is {type(self.data)}"
        )
        # Device ID for Rover is often 1 byte at offset 4 in this specific response structure.
        super()._parse_device_address(
            response_bytes, address_start_index=4, address_length_bytes=1
        )
        logger.debug(
            f"Device address parsed for '{self.device_alias}': DeviceID='{self.data.device_id}'"
        )

    def parse_charging_info(self, bs: bytearray) -> None:
        """Parses the main block of charging and status information."""
        logger.debug(f"Parsing charging info for '{self.device_alias}'...")
        assert isinstance(self.data, RoverData), (
            f"self.data is not RoverData instance in parse_chargin_info, it is {type(self.data)}"
        )
        temp_unit = self.config_manager.get(
            C.CONFIG_SECTION_DATA, C.CONFIG_KEY_TEMP_UNIT
        )
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        self.data.battery_percentage = bytes_to_int(bs, 3, 2)
        self.data.battery_voltage = bytes_to_int(bs, 5, 2, scale=0.1)
        self.data.battery_current = bytes_to_int(bs, 7, 2, scale=0.01)
        # Ensure raw temperature values are integers before bitwise ops in parse_temperature
        self.data.battery_temperature = parse_temperature(
            int(bytes_to_int(bs, 10, 1)), temp_unit  # Cast to int
        )
        self.data.controller_temperature = parse_temperature(
            int(bytes_to_int(bs, 9, 1)), temp_unit # Cast to int
        )
        # Ensure value for LOAD_STATE_MAP key is int before bitwise op
        self.data.load_status = LOAD_STATE_MAP.get(int(bytes_to_int(bs, 67, 1)) >> 7)
        self.data.load_voltage = bytes_to_int(bs, 11, 2, scale=0.1)
        self.data.load_current = bytes_to_int(bs, 13, 2, scale=0.01)
        self.data.load_power = bytes_to_int(bs, 15, 2)
        self.data.pv_voltage = bytes_to_int(bs, 17, 2, scale=0.1)
        self.data.pv_current = bytes_to_int(bs, 19, 2, scale=0.01)
        self.data.pv_power = bytes_to_int(bs, 21, 2)
        # ... (other fields)
        self.data.max_charging_power_today = bytes_to_int(bs, 33, 2) # Added this line back
        self.data.max_discharging_power_today = bytes_to_int(bs, 35, 2) # Added this line back
        self.data.charging_amp_hours_today = bytes_to_int(bs, 37, 2) # Added this line back
        self.data.discharging_amp_hours_today = bytes_to_int(bs, 39, 2) # Added this line back
        self.data.power_generation_today = bytes_to_int(bs, 41, 2) # Added this line back
        self.data.power_consumption_today = bytes_to_int(bs, 43, 2) # Added this line back
        self.data.power_generation_total = bytes_to_int(bs, 59, 4)
        # Ensure value for CHARGING_STATE_MAP key is int
        self.data.charging_status = CHARGING_STATE_MAP.get(int(bytes_to_int(bs, 68, 1)))
        logger.debug(f"Charging info parsed for '{self.device_alias}'.")

    def parse_battery_type(self, bs: bytearray) -> None:
        """Parses the configured battery type."""
        logger.debug(f"Parsing battery type for '{self.device_alias}'...")
        assert isinstance(self.data, RoverData), (
            f"self.data is not RoverData instance in parse_battery_type, it is {type(self.data)}"
        )
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        self.data.battery_type = BATTERY_TYPE_MAP.get(int(bytes_to_int(bs, 3, 2))) # Cast to int
        logger.debug(
            f"Battery type parsed for '{self.device_alias}': Type='{self.data.battery_type}'"
        )

    def parse_set_load_response(self, bs: bytearray) -> dict:
        """
        Parses the response from a "set load" command.

        Args:
            bs: The raw bytearray response.

        Returns:
            A dictionary containing the parsed response, typically including
            the function code and the new load status.
        """
        logger.debug(f"Parsing set load response for '{self.device_alias}'...")
        response_data = {}
        response_data[C.KEY_FUNCTION] = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        raw_load_status = bytes_to_int(bs, 5, 1) # Status is often in byte at offset 5
        response_data["load_set_status"] = LOAD_STATE_MAP.get(raw_load_status)
        logger.debug(
            f"Set load response parsed for '{self.device_alias}': {response_data}"
        )
        return response_data
