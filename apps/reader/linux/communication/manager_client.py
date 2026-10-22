from __future__ import annotations

import requests
import time 
from reader_core.device import Device


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
