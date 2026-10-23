"""Transport-independent facade over ReaderCore and its observation outputs."""
from reader_core import ReaderCore, Device, Observation
from typing import Protocol


class ObservationOutput(Protocol):
    def register_device(self, reader_id: str, device: Device) -> None: ...
    def publish(self, reader_id: str, observation: Observation) -> None: ...


class ReaderService:
    def __init__(self, core: ReaderCore, outputs: tuple[ObservationOutput, ...] = ()):
        # The composition supplies a fresh core; do not silently replace callbacks.
        if core.on_observation is not None or core.on_register_device is not None:
            raise ValueError("ReaderService requires a core without callbacks")
        self.core = core
        self.outputs = tuple(outputs)
        core.on_register_device = self.register_device_output
        core.on_observation = self.publish

    def ingest(self, observation: Observation) -> bool:
        return self.core.ingest(observation)

    def register_device_output(self, device: Device) -> None:
        for output in self.outputs:
            output.register_device(self.core.reader_id, device)

    def publish(self, observation: Observation) -> None:
        for output in self.outputs:
            output.publish(self.core.reader_id, observation)

    def metadata(self, *, stream_enabled: bool = False) -> dict:
        return {
            "readerId": self.core.reader_id,
            "capabilities": {"stream": stream_enabled},
            "payloadFormats": ["application/json"],
        }

    def devices(self) -> list[dict]:
        return [
            {"deviceId": device.device_id, "deviceType": device.device_type,
             "sensors": [sensor.sensor_id for sensor in device.list_sensors()]}
            for device in self.core.devices.values()
        ]
