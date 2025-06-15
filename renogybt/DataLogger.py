import json
import logging
import requests
import paho.mqtt.publish as publish
from datetime import datetime
from .ConfigManager import ConfigManager

PVOUTPUT_URL = 'http://pvoutput.org/service/r2/addstatus.jsp'

class DataLogger:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def log_remote(self, json_data):
        headers = { "Authorization" : f"Bearer {self.config_manager.get('remote_logging', 'auth_header')}" }
        req = requests.post(self.config_manager.get('remote_logging', 'url'), json = json_data, timeout=15, headers=headers)
        logging.info("Log remote 200") if req.status_code == 200 else logging.error(f"Log remote error {req.status_code}")

    def log_mqtt(self, json_data):
        logging.info(f"mqtt logging")
        user = self.config_manager.get('mqtt', 'user')
        password = self.config_manager.get('mqtt', 'password')
        auth = None if not user or not password else {"username": user, "password": password}

        publish.single(
            self.config_manager.get('mqtt', 'topic'), payload=json.dumps(json_data),
            hostname=self.config_manager.get('mqtt', 'server'), port=int(self.config_manager.get('mqtt', 'port')),
            auth=auth, client_id="renogy-bt"
        )

    def log_pvoutput(self, json_data):
        date_time = datetime.now().strftime("d=%Y%m%d&t=%H:%M")
        data = f"{date_time}&v1={json_data['power_generation_today']}&v2={json_data['pv_power']}&v3={json_data['power_consumption_today']}&v4={json_data['load_power']}&v5={json_data['controller_temperature']}&v6={json_data['battery_voltage']}"
        response = requests.post(PVOUTPUT_URL, data=data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Pvoutput-Apikey": self.config_manager.get('pvoutput', 'api_key'),
            "X-Pvoutput-SystemId":  self.config_manager.get('pvoutput', 'system_id')
        })
        print(f"pvoutput {response}")
