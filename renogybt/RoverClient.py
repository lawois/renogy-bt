import logging
from .BaseClient import BaseClient
from .Utils import bytes_to_int, parse_temperature
from .datamodels import RoverData
from . import constants as C
import asyncio
import logging # Added for module-level logger

# Read and parse BT-1/BT-2 type bluetooth modules connected to Renogy Rover/Wanderer/Adventurer

# Client-specific maps remain here
FUNCTION_MAP = {
    C.OP_CODE_READ: "READ",
    C.OP_CODE_WRITE: "WRITE",
}

logger = logging.getLogger(__name__) # Module-level logger

CHARGING_STATE_MAP = {
    0: 'deactivated',
    1: 'activated',
    2: 'mppt',
    3: 'equalizing',
    4: 'boost',
    5: 'floating',
    6: 'current limiting'
}

LOAD_STATE_MAP = {
  0: 'off',
  1: 'on'
}

BATTERY_TYPE_MAP = {
    1: 'open',
    2: 'sealed',
    3: 'gel',
    4: 'lithium',
    5: 'custom'
}

class RoverClient(BaseClient):
    def __init__(self, config_manager, on_data_callback=None, on_error_callback=None):
        super().__init__(config_manager)
        self.on_data_callback = on_data_callback
        self.on_error_callback = on_error_callback
        self.sections = [
            {C.KEY_REGISTER: 12, C.KEY_WORDS: 8, C.KEY_PARSER: self.parse_device_info},
            {C.KEY_REGISTER: 26, C.KEY_WORDS: 1, C.KEY_PARSER: self.parse_device_address},
            {C.KEY_REGISTER: 256, C.KEY_WORDS: 34, C.KEY_PARSER: self.parse_chargin_info},
            {C.KEY_REGISTER: 57348, C.KEY_WORDS: 1, C.KEY_PARSER: self.parse_battery_type}
        ]
        self.set_load_params = {C.KEY_FUNCTION: C.OP_CODE_WRITE, C.KEY_REGISTER: 266}

    async def on_data_received(self, response):
        operation = bytes_to_int(response, 1, 1)
        if operation == C.OP_CODE_WRITE: # write operation
            # For now, let's assume parse_set_load_response returns a simple dict for the callback.
            write_response_data = self.parse_set_load_response(response)
            self.on_write_operation_complete(write_response_data)
        else:
            if not isinstance(self.data, RoverData):
                logger.warning("self.data was not a RoverData instance in on_data_received, re-initializing.") # Use logger
                self.data = self._get_empty_data_container()
            await super().on_data_received(response)

    def on_write_operation_complete(self, write_data):
        logger.info(f"Write operation complete for {self.device_alias}. Response data: {write_data}") # Use logger
        if self.on_data_callback is not None:
            self.on_data_callback(self, write_data)

    def _get_empty_data_container(self):
        logger.debug(f"RoverClient._get_empty_data_container() called for {self.device_alias}")
        return RoverData()

    def set_load(self, value = 0):
        logger.info(f"Setting load to {value} for {self.device_alias}") # Use logger
        request = self.create_generic_read_request(
            self.device_id_from_config, # Use the correct device_id attribute
            self.set_load_params[C.KEY_FUNCTION],
            self.set_load_params[C.KEY_REGISTER],
            value
        )
        logger.debug(f"Set load request payload for {self.device_alias}: {request}")
        asyncio.create_task(self.ble_manager.characteristic_write_value(request))

    def parse_device_info(self, response_bytes):
        logger.debug(f"Parsing device info for {self.device_alias}...")
        assert isinstance(self.data, RoverData), f"self.data is not RoverData instance in parse_device_info, it is {type(self.data)}"
        self.data.function = FUNCTION_MAP.get(bytes_to_int(response_bytes, 1, 1))
        super()._parse_device_info(response_bytes, model_start_index=3, model_end_index=19)
        logger.debug(f"Device info parsed for {self.device_alias}: Model={self.data.model}")

    def parse_device_address(self, response_bytes):
        logger.debug(f"Parsing device address for {self.device_alias}...")
        assert isinstance(self.data, RoverData), f"self.data is not RoverData instance in parse_device_address, it is {type(self.data)}"
        super()._parse_device_address(response_bytes, address_start_index=4, address_length_bytes=1)
        logger.debug(f"Device address parsed for {self.device_alias}: DeviceID={self.data.device_id}")

    def parse_chargin_info(self, bs):
        logger.debug(f"Parsing charging info for {self.device_alias}...")
        assert isinstance(self.data, RoverData), f"self.data is not RoverData instance in parse_chargin_info, it is {type(self.data)}"
        temp_unit = self.config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_TEMP_UNIT)
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        self.data.battery_percentage = bytes_to_int(bs, 3, 2)
        self.data.battery_voltage = bytes_to_int(bs, 5, 2, scale = 0.1)
        self.data.battery_current = bytes_to_int(bs, 7, 2, scale = 0.01)
        self.data.battery_temperature = parse_temperature(bytes_to_int(bs, 10, 1), temp_unit)
        self.data.controller_temperature = parse_temperature(bytes_to_int(bs, 9, 1), temp_unit)
        self.data.load_status = LOAD_STATE_MAP.get(bytes_to_int(bs, 67, 1) >> 7)
        self.data.load_voltage = bytes_to_int(bs, 11, 2, scale = 0.1)
        self.data.load_current = bytes_to_int(bs, 13, 2, scale = 0.01)
        self.data.load_power = bytes_to_int(bs, 15, 2)
        self.data.pv_voltage = bytes_to_int(bs, 17, 2, scale = 0.1)
        self.data.pv_current = bytes_to_int(bs, 19, 2, scale = 0.01)
        self.data.pv_power = bytes_to_int(bs, 21, 2)
        self.data.max_charging_power_today = bytes_to_int(bs, 33, 2)
        self.data.max_discharging_power_today = bytes_to_int(bs, 35, 2)
        self.data.charging_amp_hours_today = bytes_to_int(bs, 37, 2)
        self.data.discharging_amp_hours_today = bytes_to_int(bs, 39, 2)
        self.data.power_generation_today = bytes_to_int(bs, 41, 2)
        self.data.power_consumption_today = bytes_to_int(bs, 43, 2)
        self.data.power_generation_total = bytes_to_int(bs, 59, 4)
        self.data.charging_status = CHARGING_STATE_MAP.get(bytes_to_int(bs, 68, 1))
        logger.debug(f"Charging info parsed for {self.device_alias}.")

    def parse_battery_type(self, bs):
        logger.debug(f"Parsing battery type for {self.device_alias}...")
        assert isinstance(self.data, RoverData), f"self.data is not RoverData instance in parse_battery_type, it is {type(self.data)}"
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        self.data.battery_type = BATTERY_TYPE_MAP.get(bytes_to_int(bs, 3, 2))
        logger.debug(f"Battery type parsed for {self.device_alias}: Type={self.data.battery_type}")

    def parse_set_load_response(self, bs):
        logger.debug(f"Parsing set load response for {self.device_alias}...")
        response_data = {}
        response_data[C.KEY_FUNCTION] = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        raw_load_status = bytes_to_int(bs, 5, 1)
        response_data['load_set_status'] = LOAD_STATE_MAP.get(raw_load_status)
        logger.debug(f"Set load response parsed for {self.device_alias}: {response_data}")
        return response_data
