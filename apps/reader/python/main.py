from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
import json

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR / "libs/python"))

from logger import Logger
from reader_core.device import Device
from reader_core.observation import Observation
from reader_core.sensor import Sensor
from reader_core.core import ReaderCore

from bluetooth_manager import BluetoothDeviceManager
from serial_manager import SerialDeviceManager

if TYPE_CHECKING:
    from bluetooth_manager import BluetoothDeviceManager
    from serial_manager import SerialDeviceManager


class Reader:
    def __init__(
            self,
            id : str | None = None,
            config_file: str = "devices_and_sensors.json",
            verbose: bool | None = None,
            static: bool | False = False 
            ):

        self.verbose = verbose
        self.reader_id = id if id is not None else "reader"
        self.static = static

        self.env = self.load_env(Path(__file__).resolve().parent.parent / "config.env")
        self.init_logger()
        Logger.info("reader_created", readerId=self.reader_id, configFile=config_file)

        self.manager_token = self.env.get("API_TOKEN_MANAGER", "token_manager")
        self.manager_url = self.env.get("INTERNAL_URL_MANAGER") or "http://127.0.0.1:3003"
        Logger.info("manager_configured", managerUrl=self.manager_url)

        self.core = ReaderCore(
            reader_id=self.reader_id,
            token=self.manager_token,
            manager_url=self.manager_url,
        )

        self.devices: dict[str, Device] = {}
        self.sensors: dict[str, Sensor] = {}

        self.config_file = config_file


        #Cargar los dipositivos y los sensores
        config_path = Path(self.config_file)
        if not config_path.is_absolute() and not config_path.exists():
            config_path = Path(__file__).resolve().parent / config_path
        try:
            config = self.load_config(config_path) if config_path.exists() else {}
        except Exception as error:
            Logger.error("config_load_failed", path=str(config_path), error=str(error))
            raise
        Logger.info("config_loaded", path=str(config_path), exists=config_path.exists())


        self.factory(config) #Cargar dispositivos y sensores desde la configuración antes de iniciar nada más

        self.bluetooth_manager = self.bluetooth_manager_from_config(config)
        self.serial_manager = self.serial_manager_from_config(config)

    async def run(self) -> None:
        Logger.info("service_starting", readerId=self.reader_id)
        managers = [
            manager
            for manager in (self.bluetooth_manager, self.serial_manager)
            if manager is not None
        ]

        if not managers:
            raise RuntimeError("No hay managers activos. Configura serial o bluetooth BLE.")

        await asyncio.gather(*(manager.start() for manager in managers))


    def handle_bluetooth_data(self, observation : Observation) -> None:
        self.handle_measurement_data(observation)

    def handle_serial_data(self, observation : Observation) -> None:
        self.handle_measurement_data(observation)

    def handle_measurement_data(self, observation: Observation) -> None:
        device_id = observation.device_id or self.reader_id
        sensor_id = observation.sensor_id or "unknown-sensor"
        raw_value = observation.simple_result


        Logger.info(
            "measurement_received",
            deviceId=device_id,
            sensorId=sensor_id,
        )
        device = self.devices.get(device_id)
        if device is None:
            if self.static:
                Logger.info("device_not_created_due_to_static_configuration", deviceId=device_id)
                return

            device = Device(
                device_id=device_id,
                device_type="device",
            )
            self.devices[device_id] = device
            self.core.add_device(device)
            Logger.info("fallback_device_created", deviceId=device_id)

        if not device.has_sensor(sensor_id):
            if self.static:
                Logger.info("sensor_not_created_due_to_static_configuration", deviceId=device_id, sensorId=sensor_id)
                return

            sensor = Sensor(
                observable_property=observation.observable_property or "unknown",
                procedure=observation.procedure or "unknown",
                feature_of_interest=observation.feature_of_interest or "unknown",
                sensor_id=sensor_id,
                device_id=device_id,
                unit=observation.unit,
            )
            self.sensors.setdefault(sensor_id, sensor)
            device.add_sensor(sensor)
            Logger.info(
                "fallback_sensor_created",
                deviceId=device_id,
                sensorId=sensor_id,
                observableProperty=sensor.observable_property,
                procedure=sensor.procedure,
                featureOfInterest=sensor.feature_of_interest,
                unit=sensor.unit,
            )
        try:
            self.core.ingest_raw_measurement(device_id, sensor_id, raw_value)
        except Exception as error:
            Logger.error("measurement_ingest_failed", deviceId=device_id, sensorId=sensor_id, error=str(error))
            raise
        Logger.info("measurement_ingested", deviceId=device_id, sensorId=sensor_id)
    
    def factory(self, config : dict): 
        
        devices_json = config.get("devices", None)
        sensors_json = config.get("sensors", None) 
        
        if devices_json is not None:  
            for device_json in devices_json:
                device = Device.fromJson( device_json, default_device_id=self.reader_id, )
                self.devices[device.device_id] = device
                self.core.add_device(device)
                Logger.info("configured_device_loaded", deviceId=device.device_id)

        if sensors_json is not None: 
            for sensor_json in sensors_json:
                sensor = Sensor.fromJson(sensor_json, default_device_id=self.reader_id)
                self.sensors[sensor.sensor_id] = sensor

                if sensor.device_id and sensor.device_id in self.devices:
                    self.devices[sensor.device_id].add_sensor(sensor)
                    Logger.info(
                        "configured_sensor_loaded",
                        deviceId=sensor.device_id,
                        sensorId=sensor.sensor_id,
                        observableProperty=sensor.observable_property,
                    )

    def bluetooth_manager_from_config(self, config: dict) -> BluetoothDeviceManager | None:

        bluetooth_json = config.get("bluetooth", {})
        ble_json = bluetooth_json.get("ble", {})

        if not ble_json.get("enabled", False):
            return None

        Logger.info("bluetooth_manager_configured")

        return BluetoothDeviceManager(
            on_measurement=self.handle_bluetooth_data,
            scan_timeout_seconds=ble_json.get("scan_timeout_seconds", 2.0),
            sleep_seconds=ble_json.get("sleep_seconds", 0.5),
        )

    def serial_manager_from_config(self, config: dict) -> SerialDeviceManager | None:
        serial_json = config.get("serial", {})
        has_configured_serial_devices = any(
            device_json.get("comm") or device_json.get("com")
            for device_json in config.get("devices", [])
        )

        if not serial_json and not has_configured_serial_devices:
            return None

        serial_devices = self.serial_devices_from_config(config)
        serial_devices.update(serial_json.get("devices", {}))
        Logger.info(
            "serial_manager_configured",
            ports=serial_json.get("ports", None),
            devices=list(serial_devices.keys()),
        )

        return SerialDeviceManager(
            on_measurement=self.handle_serial_data,
            port_glob=serial_json.get("glob", "/dev/rfcomm*"),
            ports=serial_json.get("ports", None),
            devices=serial_devices,
            baudrate=serial_json.get("baudrate", 9600),
            read_timeout=serial_json.get("read_timeout", 1.0),
            poll_seconds=serial_json.get("poll_seconds", 1.0),
            reconnect_seconds=serial_json.get("reconnect_seconds", 2.0),
        )

    def serial_devices_from_config(self, config: dict) -> dict[str, dict]:
        serial_devices = {}
        sensors_by_device = {}
        reader_static = self.config_bool(config, "static", False)

        for sensor_json in config.get("sensors", []):
            device_id = sensor_json.get("device_id", None)
            if device_id is not None:
                sensors_by_device.setdefault(device_id, []).append(sensor_json)

        for device_json in config.get("devices", []):
            comm = device_json.get("comm") or device_json.get("com")
            if not comm:
                continue

            device_id = device_json.get("device_id", None)
            metadata = {
                "device_id": device_id,
                "allow_conflicts": self.config_bool(device_json, "allow_conflicts", False),
                "static": self.config_bool(device_json, "static", False),
                "reader_static": reader_static,
            }

            sensors = sensors_by_device.get(device_id, [])
            if len(sensors) == 1:
                sensor = sensors[0]
                metadata["sensor_id"] = sensor.get("sensor_id", comm)
                metadata["observable_property"] = sensor.get("observable_property", "unknown")
                metadata["procedure"] = sensor.get("procedure", "configured-measurement")
                metadata["feature_of_interest"] = sensor.get("feature_of_interest", "unknown-feature")
                metadata["unit"] = sensor.get("unit", None)
                metadata["sensor_allow_conflicts"] = self.config_bool(sensor, "allow_conflicts", False)

            serial_devices[comm] = metadata

        return serial_devices

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

    def init_logger(self) -> None:
        Logger.init(
            os.getenv("PHONENDO_LOGS_DIR", self.env.get("PHONENDO_LOGS_DIR", str(ROOT_DIR / "logs/services"))),
            service="reader",
            verbose=self.verbose if self.verbose is not None else self.config_bool(self.env, "PHONENDO_VERBOSE", False),
            logging=self.config_bool(self.env, "PHONENDO_LOGGING", True),
            dev=self.config_bool(self.env, "PHONENDO_DEV", False),
        )

    @staticmethod
    def config_bool(json_data: dict, key: str, default: bool) -> bool:
        value = json_data.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "si", "sí"}
        return bool(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phonendo Python Reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Qué hace:
  - Carga dispositivos y sensores desde devices_and_sensors.json.
  - Escucha puertos serie configurados, incluidos RFCOMM expuestos como /dev/rfcomm*.
  - Acepta mensajes serie en JSON, sensor:valor o valor plano.
  - Completa valores planos con la configuración del puerto y del sensor.
  - Convierte cada medición en una observación SOSA/Turtle.
  - Envía la observación al Manager en /newEvent.

Configuración de conflictos:
  - En devices[] y sensors[] se puede poner "allow_conflicts": true o false.
  - Si es false y un mensaje contradice la configuración, la medición se descarta.
  - Si es true, el dato recibido puede crear/usar el nuevo device o sensor recibido.

Ejemplos:
  python3 main.py
  python3 main.py --config devices_and_sensors.json
  python3 main.py --reader-id reader-1
""",
    )
    parser.add_argument("--reader-id", dest="reader_id", default=None, help="Identificador lógico del Reader. Si no se indica, usa 'reader'.")
    parser.add_argument("--config", default="devices_and_sensors.json", help="Ruta al JSON de configuración de dispositivos, sensores y comunicaciones.")
    parser.add_argument("--verbose", action="store_true", default=None, help="Habilitar salida detallada para depuración.")
    parser.add_argument("--static", action="store_true", help="No descubrir dispositivos o sensores fuera de la configuración.")
    return parser.parse_args()



if __name__ == "__main__":

    args = parse_args()
    reader = Reader(
        id=args.reader_id,
        config_file=args.config,
        verbose=args.verbose,
        static=args.static
    )
    asyncio.run(reader.run())
