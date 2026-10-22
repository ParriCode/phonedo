from datetime import timezone
from enum import Enum
from reader_core import Observation


def observation_to_dict(observation: Observation) -> dict:
    timestamp = observation.phenomenon_time
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {
        "observation_id": observation.observation_id,
        "device_id": observation.device_id,
        "sensor_id": observation.sensor_id,
        "observable_property": observation.observable_property.value if isinstance(observation.observable_property, Enum) else observation.observable_property,
        "simple_result": observation.simple_result,
        "phenomenon_time": timestamp.isoformat(),
        "feature_of_interest": observation.feature_of_interest,
        "procedure": observation.procedure,
        "unit": observation.unit,
    }


def observation_event(reader_id: str, observation: Observation) -> dict:
    return {
        "eventType": "observation", "readerId": reader_id,
        "deviceId": observation.device_id, "payloadFormat": "application/json",
        "payload": observation_to_dict(observation),
    }
