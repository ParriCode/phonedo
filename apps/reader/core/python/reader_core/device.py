from __future__ import annotations

from typing import Dict, List

from reader_core.sensor import Sensor

class Device:
    def __init__(
        self,
        device_id: str,
        device_type: str = "device",
        _legacy_address: str = "",
        platform: str | None = None,
        **_ignored_fields,
    ) -> None:
        if not device_id:
            raise ValueError("device_id no puede estar vacío")

        self.device_id = device_id
        self.device_type = device_type
        self.platform = platform

        self._sensors: Dict[str, Sensor] = {}

    @staticmethod
    def fromJson(
        json_data: dict,
        default_device_id: str | None = None,
    ) -> "Device":
        if not isinstance(json_data, dict):
            raise ValueError("La configuración de un device debe ser un objeto JSON")

        device_id = json_data.get("device_id") or default_device_id
        if not device_id:
            raise ValueError("device_id no puede estar vacío")

        device_type = json_data.get("device_type") or json_data.get("deviceType") or "device"
        platform = json_data.get("platform")

        device = Device(
            device_id=str(device_id),
            device_type=str(device_type),
            platform=str(platform) if platform is not None else None,
        )
        device.comm = json_data.get("comm") or json_data.get("com")
        return device

    def add_sensor(self, sensor: Sensor) -> None:
        if sensor is None:
            raise ValueError("sensor no puede ser None")

        if not sensor.sensor_id:
            raise ValueError("sensor.sensor_id no puede estar vacío")

        if sensor.sensor_id in self._sensors:
            raise ValueError(
                f"Ya existe un sensor con id '{sensor.sensor_id}' "
                f"en el dispositivo '{self.device_id}'"
            )
        sensor.device_id = self.device_id
        #Añadir el sensor
        self._sensors[sensor.sensor_id] = sensor
        
    def get_sensor(self, sensor_id: str) -> Sensor:
        if not sensor_id:
            raise ValueError("sensor_id no puede estar vacío")

        try:
            return self._sensors[sensor_id]
        except KeyError:
            raise KeyError(
                f"No existe un sensor con id '{sensor_id}' "
                f"en el dispositivo '{self.device_id}'"
            )

    def remove_sensor(self, sensor_id: str) -> None:
        if not sensor_id:
            raise ValueError("sensor_id no puede estar vacío")

        if sensor_id not in self._sensors:
            raise KeyError(
                f"No existe un sensor con id '{sensor_id}' "
                f"en el dispositivo '{self.device_id}'"
            )

        del self._sensors[sensor_id]

    def list_sensors(self) -> List[Sensor]:
        return list(self._sensors.values())

    def has_sensor(self, sensor_id: str) -> bool:
        return sensor_id in self._sensors

    def sensor_count(self) -> int:
        return len(self._sensors)





    def __repr__(self) -> str:
        return (
            f"Device("
            f"device_id={self.device_id!r}, "
            f"device_type={self.device_type!r}, "
            f"platform={self.platform!r}, "
            f"sensors={list(self._sensors.keys())!r}"
            f")"
        )
