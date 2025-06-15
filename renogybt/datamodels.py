from dataclasses import dataclass, field
from typing import Optional, Dict, List

# Common base data fields if any could go here, or in BaseClient related data structure
@dataclass
class BaseDeviceData:
    # Fields from BaseClient._parse_device_info and _parse_device_address
    model: Optional[str] = None
    device_id: Optional[int] = None # This is the one read from device, not from config
    # '__device' and '__client' are added in BaseClient.on_read_operation_complete
    # They are more like metadata for the callback consumer (example.py)
    # So, not strictly part of device's own data structure.
    # We can add them in example.py or keep them as part of a wrapper if needed.
    # For now, let's keep the dataclasses focused on device-specific data.
    # function: Optional[str] = None # This was parsed in client, might need to be added if it's essential output


@dataclass
class RoverData(BaseDeviceData):
    # From parse_chargin_info
    battery_percentage: Optional[int] = None
    battery_voltage: Optional[float] = None
    battery_current: Optional[float] = None
    battery_temperature: Optional[float] = None # Assuming parse_temperature returns float
    controller_temperature: Optional[float] = None # Assuming parse_temperature returns float
    load_status: Optional[str] = None # 'on' or 'off'
    load_voltage: Optional[float] = None
    load_current: Optional[float] = None
    load_power: Optional[int] = None
    pv_voltage: Optional[float] = None
    pv_current: Optional[float] = None
    pv_power: Optional[int] = None
    max_charging_power_today: Optional[int] = None
    max_discharging_power_today: Optional[int] = None
    charging_amp_hours_today: Optional[int] = None
    discharging_amp_hours_today: Optional[int] = None
    power_generation_today: Optional[int] = None
    power_consumption_today: Optional[int] = None
    power_generation_total: Optional[int] = None
    charging_status: Optional[str] = None # e.g., 'mppt', 'boost'

    # From parse_battery_type
    battery_type: Optional[str] = None # e.g., 'open', 'lithium'

    # From parse_set_load_response (for write operations)
    # This might be better as a separate dataclass if write ops return different structures.
    # For now, including here with Optional if it's part of the same data object sent to callback.
    # However, current implementation in RoverClient calls on_write_operation_complete separately.
    # Let's assume the callback primarily receives read data.
    # load_status_write_response: Optional[int] = None

    # function is parsed in multiple places, usually just for logging or confirming response type.
    # If it's consistently needed by the end-user, it can be added.
    # For now, assuming the primary data fields are the most important.
    function: Optional[str] = None


@dataclass
class BatteryData(BaseDeviceData):
    # From parse_cell_volt_info
    cell_count: Optional[int] = None
    # Using Dict for cell_voltages and temperatures as the number of cells/sensors can vary.
    # Example: cell_voltages = {0: 3.3, 1: 3.31, ...}
    cell_voltages: Dict[int, float] = field(default_factory=dict)

    # From parse_cell_temp_info
    sensor_count: Optional[int] = None
    temperatures: Dict[int, float] = field(default_factory=dict) # Temperatures from sensors

    # From parse_battery_info
    current: Optional[float] = None # Battery current
    voltage: Optional[float] = None # Battery voltage (overall)
    remaining_charge: Optional[float] = None # Ah
    capacity: Optional[float] = None # Ah

    # function is parsed in multiple places
    function: Optional[str] = None

# TODO: Add dataclasses for InverterClient, DCChargerClient, RoverHistoryClient if in scope.
# For now, focusing on RoverClient and BatteryClient.
