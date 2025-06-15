# -*- coding: utf-8 -*-
"""
renogybt.DataLogger
~~~~~~~~~~~~~~~~~~~

This module provides the `DataLogger` class, which is responsible for
sending device data to various external logging services based on the
application's configuration.

Supported logging targets include:
- A remote HTTP endpoint.
- An MQTT broker.
- PVOutput.org.

The DataLogger retrieves configuration for these services using the
`ConfigManager` and formats data appropriately for each target.
"""
import json
import logging
import requests
import paho.mqtt.publish as publish
from datetime import datetime
from .ConfigManager import ConfigManager
from . import constants as C # For config keys

logger = logging.getLogger(__name__)


class DataLogger:
    """
    Handles logging of device data to configured external services.

    This class uses a `ConfigManager` instance to determine which logging
    services are enabled and to get their respective configurations (e.g.,
    URL, API keys, MQTT broker details).

    Args:
        config_manager (ConfigManager): An instance of `ConfigManager`
                                        to access logging configurations.
    """

    # PVOutput.org API endpoint for adding status updates.
    PVOUTPUT_URL = "http://pvoutput.org/service/r2/addstatus.jsp"

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        logger.info("DataLogger initialized.")

    def log_remote(self, json_data: dict) -> None:
        """
        Logs data to a remote HTTP endpoint.

        Retrieves URL and authentication header from `config.ini` under the
        `[remote_logging]` section.

        Args:
            json_data: A dictionary containing the data to be logged (JSON serializable).
        """
        url = self.config_manager.get(C.CONFIG_SECTION_REMOTE_LOGGING, C.CONFIG_KEY_RL_URL)
        auth_header_val = self.config_manager.get(C.CONFIG_SECTION_REMOTE_LOGGING, C.CONFIG_KEY_RL_AUTH_HEADER)

        if not url:
            logger.warning("Remote logging enabled but URL is not configured. Skipping.")
            return

        headers = {}
        if auth_header_val:
            headers["Authorization"] = f"Bearer {auth_header_val}"

        logger.debug(f"Attempting to log to remote URL: {url} with headers: {list(headers.keys())}") # Don't log auth_header_val itself
        try:
            req = requests.post(url, json=json_data, timeout=15, headers=headers)
            if req.status_code == 200 or req.status_code == 201: # Common success codes
                logger.info(f"Successfully logged data to remote endpoint {url}. Status: {req.status_code}")
            else:
                logger.error(
                    f"Failed to log data to remote endpoint {url}. Status: {req.status_code}, Response: {req.text[:200]}" # Log snippet of response
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during remote logging to {url}: {e}", exc_info=True)


    def log_mqtt(self, json_data: dict) -> None:
        """
        Logs data to an MQTT broker.

        Retrieves MQTT server, port, topic, user, and password from `config.ini`
        under the `[mqtt]` section.

        Args:
            json_data: A dictionary containing the data to be published (JSON serializable).
        """
        server = self.config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_SERVER)
        port_str = self.config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_PORT)
        topic = self.config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_TOPIC)
        user = self.config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_USER)
        password = self.config_manager.get(C.CONFIG_SECTION_MQTT, C.CONFIG_KEY_MQTT_PASSWORD)

        if not server or not topic or not port_str:
            logger.warning("MQTT logging enabled but server, port, or topic is not configured. Skipping.")
            return

        try:
            port = int(port_str)
        except ValueError:
            logger.error(f"Invalid MQTT port configured: '{port_str}'. Skipping MQTT logging.")
            return

        auth = None
        if user and password: # Only set auth if both user and password are provided
            auth = {"username": user, "password": password}
            logger.debug(f"MQTT logging with authentication for user '{user}'.")
        else:
            logger.debug("MQTT logging without authentication.")

        try:
            logger.info(f"Publishing data to MQTT topic '{topic}' on server '{server}:{port}'.")
            publish.single(
                topic,
                payload=json.dumps(json_data), # Ensure payload is a string
                hostname=server,
                port=port,
                auth=auth,
                client_id="renogy-bt", # Consider making client_id configurable
            )
            logger.info("Data successfully published to MQTT.")
        except Exception as e: # paho.mqtt.publish can raise various exceptions
            logger.error(f"Failed to publish data to MQTT: {e}", exc_info=True)


    def log_pvoutput(self, json_data: dict) -> None:
        """
        Logs data to PVOutput.org.

        Formats data according to PVOutput API requirements using specific keys
        (defined in `constants.py` like `KEY_PVOUTPUT_...`). Retrieves API key
        and System ID from `config.ini` under the `[pvoutput]` section.

        Args:
            json_data: A dictionary containing the data relevant for PVOutput.
                       Expected keys are defined in `constants.py` (e.g.,
                       `C.KEY_PVOUTPUT_POWER_GENERATION_TODAY`).
        """
        api_key = self.config_manager.get(C.CONFIG_SECTION_PVOUTPUT, C.CONFIG_KEY_PV_API_KEY)
        system_id = self.config_manager.get(C.CONFIG_SECTION_PVOUTPUT, C.CONFIG_KEY_PV_SYSTEM_ID)

        if not api_key or not system_id:
            logger.warning("PVOutput logging enabled but API Key or System ID is not configured. Skipping.")
            return

        # Ensure all required keys for PVOutput are present in json_data
        # These keys should match those used in example.py when constructing the payload
        required_keys = [
            C.KEY_PVOUTPUT_POWER_GENERATION_TODAY, C.KEY_PVOUTPUT_PV_POWER,
            C.KEY_PVOUTPUT_POWER_CONSUMPTION_TODAY, C.KEY_PVOUTPUT_LOAD_POWER,
            C.KEY_PVOUTPUT_CONTROLLER_TEMP, C.KEY_PVOUTPUT_BATTERY_VOLTAGE
        ]
        if not all(key in json_data and json_data[key] is not None for key in required_keys):
            logger.warning(f"Skipping PVOutput logging due to missing data fields. Required: {required_keys}, Have: {list(json_data.keys())}")
            return

        date_time_str = datetime.now().strftime("d=%Y%m%d&t=%H:%M")
        # PVOutput parameter names (v1, v2, etc.) are fixed by their API.
        # Values correspond to specific metrics.
        # Power generation (v1) and consumption (v3) are typically in WattHours (Wh).
        # Power values (v2, v4) are in Watts (W).
        # Ensure units are consistent with PVOutput expectations.
        # The values from Renogy devices might need conversion (e.g. kWh to Wh).
        # Assuming data in json_data is already in correct units or scale for PVOutput.
        data_payload_str = (
            f"{date_time_str}"
            f"&v1={json_data[C.KEY_PVOUTPUT_POWER_GENERATION_TODAY]}"  # Energy Generation (Wh)
            f"&v2={json_data[C.KEY_PVOUTPUT_PV_POWER]}"                # Power Generation (W)
            f"&v3={json_data[C.KEY_PVOUTPUT_POWER_CONSUMPTION_TODAY]}" # Energy Consumption (Wh)
            f"&v4={json_data[C.KEY_PVOUTPUT_LOAD_POWER]}"              # Power Consumption (W)
            f"&v5={json_data[C.KEY_PVOUTPUT_CONTROLLER_TEMP]}"         # Temperature (°C)
            f"&v6={json_data[C.KEY_PVOUTPUT_BATTERY_VOLTAGE]}"         # Voltage (V)
        )

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Pvoutput-Apikey": api_key,
            "X-Pvoutput-SystemId": system_id,
        }

        logger.info(f"Sending data to PVOutput for System ID {system_id}.")
        logger.debug(f"PVOutput payload: {data_payload_str}") # Be mindful if this contains sensitive info indirectly
        try:
            response = requests.post(self.PVOUTPUT_URL, data=data_payload_str, headers=headers, timeout=20)
            logger.info(f"PVOutput response: Status={response.status_code}, Text='{response.text.strip()}'")
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during PVOutput logging: {e}", exc_info=True)
