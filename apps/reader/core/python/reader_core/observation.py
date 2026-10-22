from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from enum import Enum
from uuid import uuid4

@dataclass
class Observation:
    observable_property: str
    simple_result: Any
    phenomenon_time: datetime
    feature_of_interest: str
    procedure: str
    
    device_id: Optional[str] = None
    sensor_id: Optional[str] = None
    unit: Optional[str] = None
    observation_id: str = field(default_factory=lambda: uuid4().hex)


    def to_dict(self) -> dict:
        timestamp = self.phenomenon_time
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return {
            "observation_id": self.observation_id,
            "device_id": self.device_id,
            "sensor_id": self.sensor_id,
            "observable_property": self.observable_property.value if isinstance(self.observable_property, Enum) else self.observable_property,
            "simple_result": self.simple_result,
            "phenomenon_time": timestamp.isoformat(),
            "feature_of_interest": self.feature_of_interest,
            "procedure": self.procedure,
            "unit": self.unit,
        }
