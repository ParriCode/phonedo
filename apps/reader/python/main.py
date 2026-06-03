from __future__ import annotations

import argparse
import asyncio
import re
import secrets
import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
import json
from reader_core.device import Device
from reader_core.sensor import Sensor
from reader_core.core import ReaderCore

from bluetooth_manager import BluetoothDeviceManager

if TYPE_CHECKING:
    from bluetooth_manager import BluetoothDeviceManager, BluetoothObservation

DEFAULT_SCAN_INTERVAL_SECONDS = 15.0
DEFAULT_READER_MAC = "02:22:22:22:22:22"


class Reader:
    def __init__(
            self,
            mac : str | None = None,
            id : str | None = None,
            mac_policy: str = "auto",
            config_file: str = "devices_and_sensors.json",
            ):
        
        print("Creando Reader")
        self.mac = self.resolve_reader_mac(mac, mac_policy)
        self.reader_id = id if id is not None else self.mac

        self.env = self.load_env(Path(__file__).resolve().parent.parent / "config.env")

        manager_token = self.env.get("API_TOKEN_MANAGER", "token_manager")
        manager_url = self.get_manager_url()

        self.core = ReaderCore(
            reader_id=self.reader_id,
            token=manager_token,
            manager_url=manager_url,
        )

        self.devices: dict[str, Device] = {}
        self.sensors: dict[str, Sensor] = {}

        self.config_file = config_file


        #Cargar los dipositivos y los sensores
        config_path = Path(self.config_file)
        if not config_path.is_absolute() and not config_path.exists():
            config_path = Path(__file__).resolve().parent / config_path
        config = self.load_config(config_path) if config_path.exists() else {}
        self.factory(config)

        self.bluetooth_manager = self.bluetooth_manager_from_config(config) #ahora mismo en cada medición le llegará esta puta mierda

    async def run(self) -> None:
        await self.bluetooth_manager.start()
        
            
    

    def get_manager_url(self) -> str:
        manager_url = self.env.get("INTERNAL_URL_MANAGER")
        if manager_url:
            return manager_url

        register_url = self.env.get("INTERNAL_URL_MANAGER_REGISTER_DEVICE")
        if register_url and register_url.endswith("/registerDevice"):
            return register_url[: -len("/registerDevice")]

        return "http://127.0.0.1:3003"


    def handle_bluetooth_data(self, observation : BluetoothObservation) -> None:
        device_id, mac_address = self.resolve_observation_device(observation)
        sensor_id = observation.sensor_id or "unknown-sensor"
        raw_value = observation.value

        if device_id not in self.devices.keys():
            device = Device(
                device_id=device_id,
                device_type=getattr(observation, "device_type", "bluetooth") or "bluetooth",
                mac_address=mac_address,
            ) 
            self.devices[device_id] = device
            self.core.add_device(device)
            

        if not self.devices[device_id].has_sensor(sensor_id):
            sensor = Sensor(
                observable_property=getattr(observation, "observation_property", "unknown") or "unknown",
                procedure=getattr(observation, "procedure", "") or "unknown",
                feature_of_interest=getattr(observation, "feature_of_interest", "") or "unknown",
                sensor_id=sensor_id,
                device_id=device_id,
                unit=getattr(observation, "unit", None) or "Unknown",
            )
            self.sensors.setdefault(sensor_id, sensor)
            self.devices[device_id].add_sensor(sensor)
        self.core.ingest_raw_measurement(device_id, sensor_id, raw_value)

    def resolve_observation_device(self, observation: BluetoothObservation) -> tuple[str, str]:
        obs_mac = getattr(observation, "mac", "") or ""
        obs_device_id = getattr(observation, "device_id", "") or ""

        if obs_mac.lower() == "unknown" or not obs_mac:
            return obs_device_id or self.reader_id, self.mac

        return obs_device_id or obs_mac, obs_mac
    
    def factory(self, config : dict): 
        
        devices_json = config.get("devices", None)
        sensors_json = config.get("sensors", None) 
        
        if devices_json is not None:  
            for device_json in devices_json:
                device = self.device_from_json(device_json)
                self.devices[device.device_id] = device
                self.core.add_device(device)

        if sensors_json is not None: 
            for sensor_json in sensors_json:
                sensor = self.sensor_from_json(sensor_json)
                self.sensors[sensor.sensor_id] = sensor

                if sensor.device_id and sensor.device_id in self.devices:
                    self.devices[sensor.device_id].add_sensor(sensor)

    def bluetooth_manager_from_config(self, config: dict) -> BluetoothDeviceManager:

        bluetooth_json = config.get("bluetooth", {})
        ble_json = bluetooth_json.get("ble", {})
        rfcomm_json = bluetooth_json.get("rfcomm", {})

        transports = set(bluetooth_json.get("transports", ["RFCOMM"]))
        rfcomm_devices = self.rfcomm_devices_from_config(config)
        rfcomm_devices.update(rfcomm_json.get("devices", {}))

        return BluetoothDeviceManager(
            on_measurement=self.handle_bluetooth_data,
            transports=transports,
            scan_timeout_seconds=ble_json.get("scan_timeout_seconds", 2.0),
            ble_sleep_seconds=ble_json.get("sleep_seconds", 0.5),
            rfcomm_ports=rfcomm_json.get("ports", None),
            rfcomm_devices=rfcomm_devices,
            rfcomm_baudrate=rfcomm_json.get("baudrate", 9600),
            rfcomm_read_timeout=rfcomm_json.get("read_timeout", 1.0),
            rfcomm_poll_seconds=rfcomm_json.get("poll_seconds", 1.0),
            rfcomm_reconnect_seconds=rfcomm_json.get("reconnect_seconds", 2.0),
        )

    def rfcomm_devices_from_config(self, config: dict) -> dict[str, dict]:
        rfcomm_devices = {}
        sensors_by_device = {}

        for sensor_json in config.get("sensors", []):
            device_id = sensor_json.get("device_id", None)
            if device_id is not None:
                sensors_by_device.setdefault(device_id, []).append(sensor_json)

        for device_json in config.get("devices", []):
            comm = device_json.get("comm") or device_json.get("com") or device_json.get("source")
            if not comm:
                continue

            device_id = device_json.get("device_id", None)
            metadata = {
                "mac": device_json.get("mac") or device_json.get("mac_address") or self.mac,
                "device_id": device_id,
                "device_type": device_json.get("device_type") or device_json.get("deviceType") or "bluetooth",
            }

            sensors = sensors_by_device.get(device_id, [])
            if len(sensors) == 1:
                sensor = sensors[0]
                metadata["sensor_id"] = sensor.get("sensor_id", comm)
                metadata["observable_property"] = sensor.get("observable_property", "unknown")
                metadata["procedure"] = sensor.get("procedure", "configured-measurement")
                metadata["feature_of_interest"] = sensor.get("feature_of_interest", "unknown-feature")
                metadata["unit"] = sensor.get("unit", None)

            rfcomm_devices[comm] = metadata

        return rfcomm_devices

        
    def device_from_json(self, json_data : dict ) -> Device:
        if not isinstance(json_data, dict):
            raise ValueError("La configuración de un device debe ser un objeto JSON")

        mac         = ( json_data.get("mac")       or json_data.get("mac_address") or self.mac )
        device_id   = ( json_data.get("device_id") or mac or self.reader_id)
        device_type = json_data.get("device_type") or json_data.get("deviceType") or "bluetooth"
        platform = json_data.get("platform")

        device = Device(
            device_id=str(device_id),
            device_type=str(device_type),
            mac_address=str(mac),
            platform=str(platform) if platform is not None else None,
        )

        device.comm = json_data.get("comm") or json_data.get("com") or json_data.get("source")

        return device

        
    def sensor_from_json(self, json_data : dict ) -> Sensor:
        if not isinstance(json_data, dict):
            raise ValueError("La configuración de un sensor debe ser un objeto JSON")

        sensor_id           = json_data.get("sensor_id", None) 
        device_id           = json_data.get("device_id", None) 
        procedure           = json_data.get("procedure", None)
        feature_of_interest = json_data.get("feature_of_interest", None )
        observable_property = json_data.get("observable_property" , None )
        unit                = json_data.get("unit" , None )
        
        if observable_property is None:
            observable_property = "unknown"
        if procedure is None:
            procedure = "configured-measurement"
        if feature_of_interest is None:
            feature_of_interest = "unknown-feature"

        sensor = Sensor(
            observable_property=observable_property,
            procedure=procedure,
            feature_of_interest=feature_of_interest,
            sensor_id=sensor_id,
            device_id=device_id,
            unit=unit,
        )

        if device_id is not None:
            sensor.device_id = device_id

        return sensor


    @staticmethod
    def load_config(path : Path) -> dict[ str : dict ]: 
        """
        Read the file devies_and_sensors.json and load it to dict.
        This file contains the configuration to understand devices and sensors entry data
        """
        try:
            with open(path, "r") as  file_: 
                return  json.load(file_)
        except FileNotFoundError: 
            #Sino existe el archivo y SE HA ESPECIFICADO , debe de mostrar error
            raise FileNotFoundError(f"No existe el archivo: {path}")
        except json.JSONDecodeError as error:
            raise ValueError(f"Error al cargar el json: {error}")

    @staticmethod
    def resolve_reader_mac(mac: str | None, mac_policy: str) -> str:
        if mac:
            return mac

        if mac_policy == "random":
            return Reader.random_local_mac()

        if mac_policy == "default":
            return DEFAULT_READER_MAC

        detected = Reader.get_system_mac()
        return detected or DEFAULT_READER_MAC

    @staticmethod
    def get_system_mac() -> str | None:
        try:
            result = subprocess.run(
                ["bluetoothctl", "show"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            match = re.search(r"Controller\s+([0-9A-Fa-f:]{17})", result.stdout)
            if match:
                return match.group(1).lower()
        except Exception:
            pass

        node = uuid.getnode()
        if (node >> 40) % 2 == 0:
            return ":".join(f"{(node >> bits) & 0xff:02x}" for bits in range(40, -1, -8))

        return None

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phonendo Python Reader")
    parser.add_argument("--reader-id", dest="reader_id", default=None)
    parser.add_argument("--mac", default=None)
    parser.add_argument("--mac-policy", choices=["auto", "random", "default"], default="auto")
    parser.add_argument("--config", default="devices_and_sensors.json")
    parser.add_argument("--allow-conflicts", action="store_true")
    return parser.parse_args()



if __name__ == "__main__":

    print("iniciando")
    args = parse_args()
    reader = Reader(
        mac=args.mac,
        id=args.reader_id,
        mac_policy=args.mac_policy,
        config_file=args.config,
    )
    asyncio.run(reader.run())
