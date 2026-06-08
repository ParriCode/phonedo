# reader_core.py

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, Optional

import requests

from logger import Logger
from reader_core.device import Device
from reader_core.observation import Observation
from reader_core.sensor import Sensor
from reader_core.serializer import SosaTTLSerializer
from uuid import uuid4


@dataclass
class ReaderConfig:
    enable_bluetooth: bool = True
    enable_http: bool = True
    enable_local: bool = True
    manager_url: str = ""
    manager_token: str = ""


class ManagerClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        send_observation_path: str = "/newEvent",
        timeout_seconds: int = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.send_observation_path = send_observation_path
        self.timeout_seconds = timeout_seconds

    def send_observation_ttl(self, ttl: str, reader_id : str , device_id : str ) -> None:
        if not ttl:
            raise ValueError("ttl no puede estar vacío")

        if not reader_id:
            raise ValueError("reader_id no puede estar vacío")

        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError(f"manager_url inválida: {self.base_url!r}")

        headers = {
            "Accept": "application/json, text/plain",
            "Content-Type": "application/json",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        url = f"{self.base_url}{self.send_observation_path}"
        payload = {
            "token": self.token,
            "eventType": "observation",
            "payloadFormat": "text/turtle",
            "payload": ttl,
            "deviceId": device_id,
            "readerId": reader_id,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException:
            raise

        if not response.ok:
            raise RuntimeError(
                f"Error HTTP comunicando con Manager. "
                f"Status={response.status_code}. Body={response.text}"
            )

    def register_device(self, reader_id : str ,  device: Device) -> None:
        if reader_id is None: 
            raise ValueError("reader_id no puede ser None")
        if device is None:
            raise ValueError("device no puede ser None")

        payload = {
            "token": self.token,
            "schemaVersion": "phonendo.event.v1",
            "readerId": reader_id,
            "deviceId": device.device_id,
            "deviceType": device.device_type,
            "creationDatetime": int(time.time() * 1000),
        }
        response = requests.post(
            f"{self.base_url}/registerDevice",
            json=payload,
            headers={
                "Accept": "application/json, text/plain",
                "Content-Type": "application/json",
            },
            timeout=self.timeout_seconds,
        )

        if not response.ok:
            raise RuntimeError(
                f"Error HTTP registrando device en Manager. "
                f"Status={response.status_code}. Body={response.text}"
            )

class ReaderCore:
    def __init__(
        self,
        reader_id : Optional[str] = None, 
        token: Optional[str] = None, 
        manager_url : Optional[str] = None, 

        config: Optional[ReaderConfig] = None,
        allow_new_devices: bool = True,
        allow_new_sensors: bool = True,
        manager_client: Optional[ManagerClient] = None,
        on_register_device: Optional[Callable[[str, Device], None]] = None,
        on_send: Optional[Callable[[str, str, str], None]] = None,
    ) -> None:
        self.reader_id = reader_id or str(uuid4())
        self.devices: Dict[str, Device] = {}
        self.serializer = SosaTTLSerializer()
        self.config = config or ReaderConfig()
        self.allow_new_devices = allow_new_devices
        self.allow_new_sensors = allow_new_sensors
        self.manager_client = manager_client or ManagerClient(
            base_url=manager_url or self.config.manager_url,
            token=token or self.config.manager_token,
        )
        self.on_register_device = on_register_device
        self.on_send = on_send


    def register_device(self, device: Device) -> None:
        """
        Registra el dispositivo localmente y también en el Manager.
        """
        self.add_device(device)
        register = self.on_register_device or self.manager_client.register_device
        register(self.reader_id, device)

    def add_device(self, device: Device) -> None:
        if device is None:
            raise ValueError("device no puede ser None")

        if not device.device_id:
            raise ValueError("device.device_id no puede estar vacío")

        if device.device_id in self.devices:
            raise ValueError(
                f"Ya existe un dispositivo con id '{device.device_id}'"
            )

        #añadir el dispositivo
        self.devices[device.device_id] = device

    def remove_device(self, device_id: str) -> bool:
        if not device_id:
            raise ValueError("device_id no puede estar vacío")

        if device_id not in self.devices:
            return False

        del self.devices[device_id]
        return True

    def get_device(self, device_id: str) -> Device | None :
        if not device_id:
            raise ValueError("device_id no puede estar vacío")
        return self.devices.get(device_id, None)

    def load_devices_from_config(self, config: dict, default_device_id: str | None = None) -> None:
        for device_json in config.get("devices", []):
            device = Device.fromJson(device_json, default_device_id=default_device_id or self.reader_id)
            self.register_device(device)
            Logger.info("configured_device_loaded", deviceId=device.device_id)

        for sensor_json in config.get("sensors", []):
            sensor = Sensor.fromJson(sensor_json)
            device = self.get_device(sensor.device_id) if sensor.device_id else None
            if device is None:
                continue
            device.add_sensor(sensor)
            Logger.info(
                "configured_sensor_loaded",
                deviceId=sensor.device_id,
                sensorId=sensor.sensor_id,
                observableProperty=sensor.observable_property,
            )

    def handle_measurement_data(self, observation: Observation, send: bool = True) -> Observation | None:
        if observation is None:
            raise ValueError("observation no puede ser None")

        device_id = observation.device_id or self.reader_id
        sensor_id = observation.sensor_id or "unknown-sensor"

        device = self.get_device(device_id)
        if device is None:
            if not self.allow_new_devices:
                return None
            device = Device(device_id=device_id, device_type="device")
            self.register_device(device)

        if not device.has_sensor(sensor_id):
            if not self.allow_new_sensors:
                return None
            sensor = Sensor(
                observable_property=observation.observable_property or "unknown",
                procedure=observation.procedure or "unknown",
                feature_of_interest=observation.feature_of_interest or "unknown",
                sensor_id=sensor_id,
                device_id=device_id,
                unit=observation.unit,
            )
            device.add_sensor(sensor)

        try:
            ingested = self.ingest_raw_measurement(
                device_id,
                sensor_id,
                observation.simple_result,
                phenomenon_time=observation.phenomenon_time,
                send=send,
            )
        except Exception as error:
            raise
        return ingested

    def ingest_raw_measurement(
        self,
        device_id: str,
        sensor_id: str,
        raw_value: Any,
        phenomenon_time: Optional[datetime] = None,
        send: bool = True,
    ) -> Observation:
        """
        Recibe una medición cruda, busca el dispositivo y sensor,
        construye una Observation y opcionalmente la envía al Manager.
        """
        device = self.get_device(device_id)
        if device is None:
            raise KeyError(f"No existe el dispositivo '{device_id}'")
        sensor = device.get_sensor(sensor_id)

        observation = sensor.build_observation(
            raw_value=raw_value,
            phenomenon_time=phenomenon_time or datetime.now(timezone.utc),
        )

        if send:
            self.send_observation(observation)

        return observation

    def send_observation(
        self,
        observation: Observation,
       # device: Device,
    ) -> None:
        """Serializa una Observation en SOSA TTL y la manda al Manager."""
        if observation is None:
            raise ValueError("observation no puede ser None")

        if not observation.device_id:
            raise ValueError("observation.device_id no puede estar vacío")

        if self.get_device(observation.device_id) is None:
            raise KeyError(f"No existe el dispositivo '{observation.device_id}'")

        ttl = self.serializer.serialize(
            observation=observation,
        )

        sender = self.on_send or self.manager_client.send_observation_ttl
        sender(ttl, self.reader_id,  observation.device_id)
