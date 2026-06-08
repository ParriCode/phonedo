from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from reader_core.observation import Observation


class Sensor:
    """
    Sensor lógico mínimo usado por el Reader.

    Un sensor simple no interpreta protocolos ni lee hardware. Solo mantiene
    los metadatos necesarios para convertir un valor recibido en Observation.
    """

    def __init__(
        self,
        observable_property: str,
        procedure: str,
        feature_of_interest: str,
        sensor_id: str | None = None,
        unit: str | None = None,
        device_id: str | None = None,
    ) -> None:
        self.sensor_id = sensor_id or str(uuid4())
        self.observable_property = observable_property
        self.procedure = procedure
        self.feature_of_interest = feature_of_interest
        self.unit = unit
        self.device_id = device_id

    @staticmethod
    def fromJson(json_data: dict, default_device_id: str | None = None) -> "Sensor":
        if not isinstance(json_data, dict):
            raise ValueError("La configuración de un sensor debe ser un objeto JSON")

        return Sensor(
            observable_property=json_data.get("observable_property", "unknown"),
            procedure=json_data.get("procedure", "configured-measurement"),
            feature_of_interest=json_data.get("feature_of_interest", "unknown-feature"),
            sensor_id=json_data.get("sensor_id", "unknown"),
            device_id=json_data.get("device_id", default_device_id),
            unit=json_data.get("unit", None),
        )

    def build_observation(
        self,
        raw_value: Any,
        phenomenon_time: datetime | None = None,
    ) -> Observation:
        return Observation(
            observable_property=self.observable_property,
            simple_result=raw_value,
            phenomenon_time=phenomenon_time or datetime.now(timezone.utc),
            feature_of_interest=self.feature_of_interest,
            procedure=self.procedure,
            sensor_id=self.sensor_id,
            device_id=self.device_id,
            unit=self.unit,
        )

    def addObservation(
        self,
        _simple_result: Any,
        _phenomenom_time: datetime | None = None,
    ) -> Observation:
        return self.build_observation(_simple_result, _phenomenom_time)
