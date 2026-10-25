from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
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
