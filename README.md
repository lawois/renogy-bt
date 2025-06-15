# Renogy BT
![256924763-940c205e-738d-4a68-982f-1695c80bfed5](https://github.com/cyrils/renogy-bt/assets/5549113/bcdef6ec-efc9-44fd-af70-67165cf6862e)

Cross-platform Python library to read Renogy¹ Solar Charge Controllers and Smart Batteries using  [BT-1](https://www.renogy.com/bt-1-bluetooth-module-new-version/) or [BT-2](https://www.renogy.com/bt-2-bluetooth-module/) type (RS232 or RS485)  bluetooth modules. Tested with **Rover** / **Wanderer** series charge controllers, but it might also work with other  "SRNE like" devices like Rich Solar, PowMr etc. See the list of [compatible devices](#compatibility). It can also upload data to local **MQTT** broker, **PVOutput** cloud or your own custom server.

## Dependencies
You will need [Python](https://www.python.org/downloads/) 3.6 or above in your system. In some platforms you may have to create python virtual environment. Then install dependencies by running the command:
```sh
python3 -m pip install -r requirements.txt
```
This library should work on any modern Linux/Windows/Mac platforms that supports [Bleak](https://github.com/hbldh/bleak). 

## Example
Each device needs a `config.ini` file. Update the config file with correct values for your device's `mac_addr` (Bluetooth MAC address), `alias` (Bluetooth name, optional if MAC is correct), `type` (device model type), and `device_id` (Modbus ID, usually 1, 255, or specific for hub setups).

Below is a minimal example structure for `config.ini`:

```ini
[device]
# Bluetooth MAC address of your BT-1/BT-2 module or built-in BLE device
# On Linux, this is often case-sensitive. Use the exact address from discovery.
mac_addr = XX:XX:XX:XX:XX:XX
# Bluetooth alias/name of your device (optional if MAC is correct, but helpful)
alias = BT-TH-B00FXXXX
# Device type. See "Compatibility" section for common types.
# Examples: RNG_CTRL (Rover/Wanderer), RNG_BATT (Smart Battery), RNG_INVT (Inverter)
type = RNG_CTRL
# Modbus ID of the device. Usually 1 or 255 if directly connected.
# For devices on a Renogy Hub, this will be specific (e.g., 48 for a battery).
device_id = 1
# Number of connection retries if the initial attempt fails. (Default: 3)
connect_retries = 3
# Delay in seconds between connection retries. (Default: 5)
connect_retry_delay = 5

[data]
# Enable continuous polling of data. If false, script runs once.
enable_polling = false
# Interval in seconds for polling data (if enable_polling is true).
poll_interval = 60
# Comma-separated list of fields to include in MQTT/Remote logs. Leave empty for all.
# Example: fields = battery_voltage,pv_power,charging_status
fields =
# Temperature unit for output: C (Celsius) or F (Fahrenheit).
temperature_unit = C
# Logging level for the application. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level = INFO

# --- Other sections for logging (mqtt, remote_logging, pvoutput) ---
# [mqtt]
# enabled = false
# ...
```

The new `connect_retries`, `connect_retry_delay`, and `log_level` options provide more control over connection behavior and logging verbosity.

After setting up your `config.ini`, run the example script:

```sh
python3 ./example.py config.ini
```

**How to get mac address?**

The library will automatically list possible compatible devices discovered nearby, just run `example.py`. You can alternatively use apps like [BLE Scanner](https://play.google.com/store/apps/details?id=com.macdom.ble.blescanner).

**Output**

The exact log output will depend on your device type and the `log_level` set in `config.ini`.
With `log_level = INFO` or `DEBUG`, you should see messages similar to this (timestamps omitted for brevity):

```
INFO:example:Script started. Log level set to INFO.
INFO:example:Using configuration file: config.ini
INFO:renogybt.ConfigManager:Configuration file 'config.ini' loaded successfully.
INFO:renogybt.ConfigManager:Configuration file validation successful.
INFO:example:Initializing Renogy BT client...
INFO:renogybt.RoverClient:Initializing RoverClient for device 'My Rover' (XX:XX:XX:XX:XX:XX)
INFO:example:Device type specified in configuration: 'RNG_CTRL'
INFO:example:Starting client for device type: 'RNG_CTRL'...
INFO:renogybt.BaseClient:Starting client for 'My Rover'...
INFO:renogybt.BaseClient:Attempting to connect to 'My Rover' (XX:XX:XX:XX:XX:XX)...
DEBUG:renogybt.BaseClient:Initializing BLEManager for 'My Rover' (XX:XX:XX:XX:XX:XX)
DEBUG:renogybt.BLEManager:BLEManager initialized for MAC: XX:XX:XX:XX:XX:XX, Alias: My Rover
DEBUG:renogybt.BaseClient:Starting device discovery for 'My Rover'...
INFO:renogybt.BLEManager:Starting BLE discovery for MAC 'XX:XX:XX:XX:XX:XX' or alias 'My Rover'...
INFO:renogybt.BLEManager:Discovery finished. Found X devices.
DEBUG:renogybt.BLEManager:Discovered devices: ['YY:YY:YY:YY:YY:Y1', 'XX:XX:XX:XX:XX:XX']
INFO:renogybt.BLEManager:Found matching device: Name='My Rover', Address='XX:XX:XX:XX:XX:XX'
DEBUG:renogybt.BaseClient:Device 'My Rover' found (XX:XX:XX:XX:XX:XX), attempting to connect...
INFO:renogybt.BLEManager:Attempting to connect to device: XX:XX:XX:XX:XX:XX (Alias: My Rover)
INFO:renogybt.BLEManager:Successfully connected to XX:XX:XX:XX:XX:XX. Client connected: True
DEBUG:renogybt.BLEManager:Discovering services and characteristics...
INFO:renogybt.BaseClient:Successfully connected to BLE device: XX:XX:XX:XX:XX:XX ('My Rover')
INFO:renogybt.BaseClient:Reading section 0 for 'My Rover': Register 12, Words 8
DEBUG:renogybt.BaseClient:Sending read request for 'My Rover', section 0 (Register: 12): [1, 3, 0, 12, 0, 8, <crc_bytes>]
DEBUG:renogybt.BLEManager:Writing to characteristic <UUID_WRITE_CHAR> (Handle: <handle>): <payload_hex>
INFO:renogybt.BLEManager:Characteristic write successful.
DEBUG:renogybt.BaseClient:Raw data received by BaseClient for 'My Rover': <response_hex>
DEBUG:renogybt.BaseClient:Parsed operation code for 'My Rover': 3
INFO:renogybt.BaseClient:Read successful for 'My Rover', section 0 (Register: 12). Parsing...
DEBUG:renogybt.RoverClient:Parsing device info for 'My Rover'...
DEBUG:renogybt.BaseClient:Parsing device info (model) from response for 'My Rover'.
DEBUG:renogybt.BaseClient:Parsed model for 'My Rover': RNG-CTRL-RVR40
DEBUG:renogybt.RoverClient:Device info parsed for 'My Rover': Model='RNG-CTRL-RVR40'
DEBUG:renogybt.BaseClient:Parser parse_device_info for 'My Rover' executed successfully.
DEBUG:renogybt.BaseClient:Moving to next section 1 for 'My Rover'. Pausing briefly.
INFO:renogybt.BaseClient:Reading section 1 for 'My Rover': Register 26, Words 1
... (similar logs for other sections) ...
INFO:renogybt.BaseClient:All sections parsed for 'My Rover'. Preparing data for callback.
DEBUG:renogybt.BaseClient:Data for callback for 'My Rover': RoverData(model='RNG-CTRL-RVR40', device_id=1, function='READ', battery_percentage=87, ..., __device='My Rover', __client='RoverClient')
INFO:example:Data from 'My Rover': {'model': 'RNG-CTRL-RVR40', 'device_id': 1, 'function': 'READ', ..., 'battery_percentage': 87, ...}
INFO:renogybt.BaseClient:Polling disabled for 'My Rover'. Client will not initiate further reads.
INFO:example:Client execution finished or was stopped by user/error.
INFO:renogybt.BaseClient:Client for 'My Rover' has stopped.
INFO:renogybt.BaseClient:Disconnecting from 'My Rover'...
INFO:renogybt.BLEManager:Disconnecting from device: My Rover (XX:XX:XX:XX:XX:XX)
INFO:renogybt.BLEManager:Successfully disconnected.
INFO:renogybt.BaseClient:Disconnected from 'My Rover'.
DEBUG:renogybt.BaseClient:Setting main future result to 'Disconnected' for 'My Rover'.
```

The logged data structure for a Rover might look like this (when `log_level = DEBUG` in `config.ini` and no `fields` filter is applied, actual values will vary):
```json
{
  "model": "RNG-CTRL-RVR40",
  "device_id": 1,
  "function": "READ",
  "battery_percentage": 87,
  "battery_voltage": 12.9,
  "battery_current": 2.58,
  "battery_temperature": 25.0,
  "controller_temperature": 33.0,
  "load_status": "off",
  "load_voltage": 0.0,
  "load_current": 0.0,
  "load_power": 0,
  "pv_voltage": 17.1,
  "pv_current": 2.04,
  "pv_power": 35,
  "max_charging_power_today": 143,
  "max_discharging_power_today": 0,
  "charging_amp_hours_today": 34,
  "discharging_amp_hours_today": 0,
  "power_generation_today": 432,
  "power_consumption_today": 0,
  "power_generation_total": 426038,
  "charging_status": "mppt",
  "battery_type": "lithium",
  "__device": "My Rover",
  "__client": "RoverClient"
}
```
Note: The `example.py` converts dataclasses to dictionaries for logging, so the above structure reflects that. The `__device` and `__client` fields are metadata added by the library.

## Improved Error Handling
The library now features more specific exception classes for better error handling in your application. You can import these from `renogybt.exceptions`:
- `DeviceNotFoundError`: When the specified Bluetooth device cannot be found.
- `ConnectionError`: For issues during the connection phase to an already discovered device.
- `ReadTimeoutError`: If the device doesn't respond to a read command in time.
- `InvalidResponseError`: If the device sends unexpected or malformed data.
- `ConfigError`: For configuration-specific issues (though `ValueError` is often raised directly by `ConfigManager` for validation).
- `RenogyBTError`: The base class for all library-specific exceptions.

Your application can catch these specific exceptions to implement more granular error recovery or user feedback, similar to how `example.py` now logs them differently.

## Have multiple devices in Hub mode?

If you have multiple devices connected to a single BT-2 module (daisy chained or using [Communication Hub](https://www.renogy.com/communication-hub/)), you need to find out the individual device Id (aka address) of each of these devices. Below are some of the usual suspects:

|  | Stand-alone | Daisy-chained | Hub mode |
| :-------- | :-------- | :-------- | :-------- |
|  Controller | 255, 17 | 16, 17 | 96, 97 |
|  Battery | 255 | 33, 34, 35 | 48, 49, 50 |
|  Inverter | 255, 32 | 32 | 32 |

 If you receive no response or garbled data with above ids, connect a single device to the Hub at a time and use the default broadcast address of 255 in `config.ini` to find out the actual `device_id` from output log. Then use this device Id to connect in Hub mode.

## Compatibility
| Device | Type | Adapter | Supported |
| -------- | :-------- | :--------: | :--------: |
| Renogy Rover/Wanderer/Adventurer | Controller |  BT-1 | ✅ |
| Renogy Rover Elite RCC40RVRE | Controller | BT-2 |  ✅ |
| Renogy DC-DC Charger DCC50S | Controller | BT-2 |  ✅ |
| SRNE ML24/ML48 Series | Controller | BT-1 | ✅ |
| RICH SOLAR 20/40/60 | Controller | BT-1 | ✅ |
| Renogy RBT100LFP12S / RBT50LFP48S | Battery | BT-2 | ✅ |
| Renogy RBT100LFP12-BT / RBT200LFP12-BT (Built-in BLE) | Battery | - | ✅ |
| Renogy RBT12100LFP-BT / RBT12200LFP-BT (Pro Series) | Battery | - | ✅ |
| Renogy RIV4835CSH1S | Inverter | BT-2 | ✅ |
| Renogy Rego RIV1230RCH (Built-in BLE) | Inverter | - | ✅ |
| Renogy Smart Shunt | Shunt | - | ❌ |

## Data logging

Supports logging data to local MQTT brokers like [Mosquitto](https://mosquitto.org/) or [Home Assistant](https://www.home-assistant.io/) dashboards. You can also log it to third party cloud services like [PVOutput](https://pvoutput.org/). See the example `config.ini` structure above and the comments within for more details on configuring these sections. Note that free PVOutput accounts have a cap of one request per minute.

Example config to add to your home assistant `configuration.yaml`:
```yaml
mqtt:
  sensor:
    - name: "Solar Power"
      state_topic: "solar/state"
      device_class: "power"
      unit_of_measurement: "W"
      value_template: "{{ value_json.pv_power }}"
    - name: "Battery SOC"
      state_topic: "solar/state"
      device_class: "battery"
      unit_of_measurement: "%"
      value_template: "{{ value_json.battery_percentage }}"
# check output log for more fields
```

**Custom logging**

Should you choose to upload to your own server, the json data is posted as body of the HTTP POST call. The optional `auth_header` is sent as http header `Authorization: Bearer <auth-header>`

Example php code at the server:
```php
$headers = getallheaders();
if ($headers['Authorization'] != "Bearer 123456789") {
    header( 'HTTP/1.0 403 Forbidden', true, 403 );
    die('403 Forbidden');
}
$json_data = json_decode(file_get_contents('php://input'), true);
```

**How to get continues output?**

 The best way to get continues data is to schedule a cronjob by running `crontab -e` and insert the following command:
```sh
*/5 * * * * python3 /path/to/renogy-bt/example.py config.ini #runs every 5 mins
```
If you want to monitor real-time data, turn on polling in `config.ini` for continues streaming (default interval is 60 secs). You may also register it as a [service](https://github.com/cyrils/renogy-bt/issues/77) for added reliability.

### Disclaimer

¹This is not an official library endorsed by the device manufacturer. Renogy and all other trademarks in this repo are the property of their respective owners and their use herein does not imply any sponsorship or endorsement.

## References

 - [Olen/solar-monitor](https://github.com/Olen/solar-monitor)
 - [corbinbs/solarshed](https://github.com/corbinbs/solarshed)
 - [Renogy modbus documentation](https://github.com/cyrils/renogy-bt/discussions/94)
 - [mavenius/renogy-bt-esphome](//github.com/mavenius/renogy-bt-esphome) - ESPHome port of this project
