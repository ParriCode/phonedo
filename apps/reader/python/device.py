from __future__ import annotations

from typing import Dict, List

from sensor_base import SensorBase

class Device:
    def __init__( self, device_id: str, device_type: str, mac_address: str , platform: str | None = None,
    ) -> None:
        if not device_id:
            raise ValueError("device_id no puede estar vacío")
        
        if not mac_address:
            raise ValueError("mac_addres no puede estar vacía")
        self.device_id = device_id
        self.device_type = device_type
        self.mac_address = mac_address
        self.platform = platform

        self._sensors: Dict[str, SensorBase] = {}

    def add_sensor(self, sensor: SensorBase) -> None:
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
        
    def get_sensor(self, sensor_id: str) -> SensorBase:
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

    def list_sensors(self) -> List[SensorBase]:
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
            f"mac_address={self.mac_address!r}, "
            f"platform={self.platform!r}, "
            f"sensors={list(self._sensors.keys())!r}"
            f")"
        )
