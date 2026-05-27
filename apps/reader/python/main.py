from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from device import Device
from sensor_base import SensorBase
from core import ReaderCore
from bluetooth_manager import BluetoothDeviceManager ,   BluetoothObservation


DEFAULT_SCAN_INTERVAL_SECONDS = 15.0

class Reader:
    async def __init__(self):
        
        self.env = self.load_env(Path(__file__).resolve().parent.parent / "config.env")

        manager_token = self.env.get("API_TOKEN_MANAGER", "token_manager")
        manager_url = self.get_manager_url()

        self.core = ReaderCore(
            token=manager_token,
            manager_url=manager_url,
        )

        self.devices = dict[ str : Device]
        self.sensors = dict[str : SensorBase]



        bluetooth_manager = BluetoothDeviceManager(
                on_measurement=self.handle_bluetooth_data,
                transports={"RFCOMM"},
                rfcomm_devices={
                    "/dev/rfcomm0":{
                        "mac": "00:21:13:01:1F:91",

                    }
                }
            )

        await bluetooth_manager.start()




    def get_manager_url(self) -> str:
        manager_url = self.env.get("INTERNAL_URL_MANAGER")
        if manager_url:
            return manager_url

        register_url = self.env.get("INTERNAL_URL_MANAGER_REGISTER_DEVICE")
        if register_url and register_url.endswith("/registerDevice"):
            return register_url[: -len("/registerDevice")]

        return "http://127.0.0.1:3003"


    def handle_bluetooth_data(self, observation : BluetoothObservation) -> None:
        device_id = observation.mac
        sensor_id = observation.sensor_id
        raw_value = observation.value
        
        if device_id not in self.devices.keys():
            self.devices[device_id] = Device(
                device_id=device_id,
                device_type="bluetooth",
                mac_address=observation.mac,
            ) 

        
        self.core.ingest_raw_measurement(device_id, sensor_id, raw_value)


    @staticmethod
    def load_env(path: Path) -> dict[str, str]:
        values: dict[str, str] = {}

        if not path.exists():
            return values

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

        return values





if __name__ == "__main__":
    reader = Reader()
