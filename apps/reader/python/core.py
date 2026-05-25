# reader_core.py

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional

import requests

from device import Device
from observation import Observation
from sensor_base import SensorBase
from serializer import SosaTTLSerializer
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

        headers = {
            "Accept": "application/json, text/plain",
            "Content-Type": "application/json",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"


        response = requests.post(
            f"{self.base_url}{self.send_observation_path}",
            json={
                "token": self.token,
                "eventType": "observation",
                "payloadFormat": "text/turtle",
                "payload": ttl,
                "deviceId": device_id,
                "readerId": reader_id
            },
            headers=headers,
            timeout=self.timeout_seconds,
        )



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

        response = requests.post(
            f"{self.base_url}/registerDevice",
            json={
                "token": self.token,
                "schemaVersion": "phonendo.event.v1", 
                "readerId": reader_id,
                "deviceId": device.device_id,
                "deviceType":device.device_type,
                "serialNumber": device.serial_number,
                "macAddress": device.mac_address,
                "creationDatetime": int(time.time() * 1000),
            },
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
    ) -> None:
        self.reader_id = reader_id or str(uuid4())
        self.devices: Dict[str, Device] = {}
        self.serializer = SosaTTLSerializer()
        self.config = config or ReaderConfig()
        self.manager_client = ManagerClient(
            base_url=manager_url or self.config.manager_url,
            token=token or self.config.manager_token,
        )

    def register_device(self, device: Device) -> None:
        """
        Registra el dispositivo localmente y también en el Manager.
        """
        self.add_device(device)
        self.manager_client.register_device(self.reader_id,   device)

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

    def remove_device(self, device_id: str) -> None:
        if not device_id:
            raise ValueError("device_id no puede estar vacío")

        if device_id not in self.devices:
            raise KeyError(f"No existe el dispositivo '{device_id}'")

        del self.devices[device_id]

    def get_device(self, device_id: str) -> Device:
        if not device_id:
            raise ValueError("device_id no puede estar vacío")

        try:
            return self.devices[device_id]
        except KeyError:
            raise KeyError(f"No existe el dispositivo '{device_id}'")

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
        """
        Serializa una Observation en SOSA TTL y la manda al Manager.
        """

        if observation is None:
            raise ValueError("observation no puede ser None")

        if not observation.device_id:
            raise ValueError("observation.device_id no puede estar vacío")

        # Obtener el device por medio de la observación, únicamente comprobación.
        self.get_device(observation.device_id)

        ttl = self.serializer.serialize(
            observation=observation,
        )

        print(f"ttl que se va a enviar=:\n{ttl}")
        self.manager_client.send_observation_ttl(ttl, self.reader_id,  observation.device_id)
