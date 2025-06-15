import logging # For warnings if needed, and assertions
from .BaseClient import BaseClient
from .Utils import bytes_to_int, format_temperature
from .datamodels import BatteryData
from . import constants as C # Import constants

# Client for Renogy LFP battery with built-in bluetooth / BT-2 module

logger = logging.getLogger(__name__) # Module-level logger

FUNCTION_MAP = {
    C.OP_CODE_READ: "READ",
    C.OP_CODE_WRITE: "WRITE",
}

class BatteryClient(BaseClient):
    def __init__(self, config_manager, on_data_callback=None, on_error_callback=None):
        super().__init__(config_manager) # BaseClient __init__ logs its own message
        self.on_data_callback = on_data_callback
        self.on_error_callback = on_error_callback
        self.sections = [
            {C.KEY_REGISTER: 5000, C.KEY_WORDS: 17, C.KEY_PARSER: self.parse_cell_volt_info},
            {C.KEY_REGISTER: 5017, C.KEY_WORDS: 17, C.KEY_PARSER: self.parse_cell_temp_info},
            {C.KEY_REGISTER: 5042, C.KEY_WORDS: 6, C.KEY_PARSER: self.parse_battery_info},
            {C.KEY_REGISTER: 5122, C.KEY_WORDS: 8, C.KEY_PARSER: self.parse_device_info},
            {C.KEY_REGISTER: 5223, C.KEY_WORDS: 1, C.KEY_PARSER: self.parse_device_address}
        ]

    def _get_empty_data_container(self):
        logger.debug(f"BatteryClient._get_empty_data_container() called for {self.device_alias}")
        return BatteryData()

    def parse_cell_volt_info(self, bs):
        logger.debug(f"Parsing cell voltage info for {self.device_alias}...")
        assert isinstance(self.data, BatteryData), f"self.data is not BatteryData instance in parse_cell_volt_info, it is {type(self.data)}"
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        self.data.cell_count = bytes_to_int(bs, 3, 2)
        if self.data.cell_count is not None:
            for i in range(0, self.data.cell_count):
                self.data.cell_voltages[i] = bytes_to_int(bs, 5 + i*2, 2, scale = 0.1)
        logger.debug(f"Cell voltage info parsed for {self.device_alias}: Cell count={self.data.cell_count}")

    def parse_cell_temp_info(self, bs):
        logger.debug(f"Parsing cell temperature info for {self.device_alias}...")
        assert isinstance(self.data, BatteryData), f"self.data is not BatteryData instance in parse_cell_temp_info, it is {type(self.data)}"
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        self.data.sensor_count = bytes_to_int(bs, 3, 2)
        if self.data.sensor_count is not None:
            temp_unit = self.config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_TEMP_UNIT)
            for i in range(0, self.data.sensor_count):
                celcius = bytes_to_int(bs, 5 + i*2, 2, scale = 0.1, signed = True)
                self.data.temperatures[i] = format_temperature(celcius, temp_unit)
        logger.debug(f"Cell temperature info parsed for {self.device_alias}: Sensor count={self.data.sensor_count}")

    def parse_battery_info(self, bs):
        logger.debug(f"Parsing battery info for {self.device_alias}...")
        assert isinstance(self.data, BatteryData), f"self.data is not BatteryData instance in parse_battery_info, it is {type(self.data)}"
        self.data.function = FUNCTION_MAP.get(bytes_to_int(bs, 1, 1))
        self.data.current = bytes_to_int(bs, 3, 2, True, scale = 0.01)
        self.data.voltage = bytes_to_int(bs, 5, 2, scale = 0.1)
        self.data.remaining_charge = bytes_to_int(bs, 7, 4, scale = 0.001)
        self.data.capacity = bytes_to_int(bs, 11, 4, scale = 0.001)
        logger.debug(f"Battery info parsed for {self.device_alias}: Voltage={self.data.voltage}, Current={self.data.current}")

    def parse_device_info(self, response_bytes):
        logger.debug(f"Parsing device info for {self.device_alias}...")
        assert isinstance(self.data, BatteryData), f"self.data is not BatteryData instance in parse_device_info, it is {type(self.data)}"
        self.data.function = FUNCTION_MAP.get(bytes_to_int(response_bytes, 1, 1))
        super()._parse_device_info(response_bytes, model_start_index=3, model_end_index=19, strip_chars='\x00')
        logger.debug(f"Device info parsed for {self.device_alias}: Model={self.data.model}")

    def parse_device_address(self, response_bytes):
        logger.debug(f"Parsing device address for {self.device_alias}...")
        assert isinstance(self.data, BatteryData), f"self.data is not BatteryData instance in parse_device_address, it is {type(self.data)}"
        super()._parse_device_address(response_bytes, address_start_index=3, address_length_bytes=2)
        logger.debug(f"Device address parsed for {self.device_alias}: DeviceID={self.data.device_id}")
