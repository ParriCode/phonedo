# reader_core.py

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from reader_core.device import Device
from reader_core.observation import Observation
from reader_core.sensor import Sensor
from uuid import uuid4



class ReaderCore:
    def __init__(
        self,
        reader_id: Optional[str] = None,
        *,

        allow_new_devices: bool = True,
        allow_new_sensors: bool = True,


        on_register_device: Optional[Callable[[Device], None]] = None,
        on_observation: Optional[Callable[[Observation], None]] = None,
    ) -> None:
        self.reader_id = reader_id or str(uuid4())
        self.devices: Dict[str, Device] = {}
        self.allow_new_devices = allow_new_devices
        self.allow_new_sensors = allow_new_sensors

        self.on_register_device = on_register_device
        self.on_observation = on_observation


    def register_device(self, device: Device) -> None:
        """
        Registra el dispositivo localmente y notifica al adaptador configurado.
        """
        self.add_device(device)
        if self.on_register_device is not None:
            self.on_register_device(device)


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
            device = Device.fromJson(device_json, default_device_id=default_device_id)
            self.register_device(device)

        for sensor_json in config.get("sensors", []):
            sensor = Sensor.fromJson(sensor_json)
            device = self.get_device(sensor.device_id) if sensor.device_id else None
            if device is None:
                continue
            device.add_sensor(sensor)
           
    def ingest(self, observation: Observation, send: bool = True) -> bool:
        if observation is None:
            raise ValueError("observation no puede ser None")

        self._validate_identity(observation)
        device_id = observation.device_id
        sensor_id = observation.sensor_id

        device = self.get_device(device_id)
        if device is None:
            if not self.allow_new_devices:
                return False
            device = Device(device_id=device_id, device_type="device")
            self.register_device(device)

        if not device.has_sensor(sensor_id):
            if not self.allow_new_sensors:
                return False
            sensor = Sensor(
                observable_property=observation.observable_property,
                procedure=observation.procedure,
                feature_of_interest=observation.feature_of_interest,
                sensor_id=sensor_id,
                device_id=device_id,
                unit=observation.unit,
            )
            device.add_sensor(sensor)

        if send:
            self.send_observation(observation)

        return True


    def create_observation(
        self,
        device_id: str,
        sensor_id: str,
        value: Any,
        phenomenon_time: Optional[datetime] = None,

    ) -> Observation:
        """
        Recibe una medición cruda, busca el dispositivo y sensor,
        construye una Observation sin emitirla.
        """
        device = self.get_device(device_id)
        if device is None:
            raise KeyError(f"No existe el dispositivo '{device_id}'")
        sensor = device.get_sensor(sensor_id)

        observation = sensor.build_observation(
            raw_value=value,
            phenomenon_time=phenomenon_time or datetime.now(timezone.utc),
        )

        return observation

    def send_observation( self, observation: Observation) -> None:
        """Emite la observación sin serializarla."""
        self._validate_identity(observation)

        if self.get_device(observation.device_id) is None:
            raise KeyError(f"No existe el dispositivo '{observation.device_id}'")

        if self.on_observation is not None:
            self.on_observation(observation)

    @staticmethod
    def _validate_identity(observation: Observation) -> None:
        if observation is None:
            raise ValueError("observation no puede ser None")
        for field in ("device_id", "sensor_id"):
            value = getattr(observation, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"observation.{field} no puede estar vacío")
