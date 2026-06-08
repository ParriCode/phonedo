# sosa_ttl_serializer.py

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import json
import re


class SosaTTLSerializer:
    def serialize(self,  observation) -> str:
        device_ref = self._ph(observation.device_id)
        obs_ref = self._ph(observation.observation_id)

        property_name = self._enum_value(observation.observable_property)
        property_ref = self._ph(property_name)

        sensor_ref = self._ph(observation.sensor_id)
        feature_ref = self._ph(observation.feature_of_interest)
        procedure_ref = self._ph(observation.procedure)
        has_unit = self._has_unit(observation.unit)
        result_block = self._result_block(observation, has_unit)
        qudt_prefixes = """@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
""" if has_unit else ""


        return f"""@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix time: <http://www.w3.org/2006/time#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ph: <urn:phonendo:> .
{qudt_prefixes}

{device_ref} a sosa:Platform .

{sensor_ref}
    a sosa:Sensor ;
    sosa:isHostedBy {device_ref} ;
    sosa:observes {property_ref} .

{property_ref} a sosa:ObservableProperty .
{feature_ref} a sosa:FeatureOfInterest .
{procedure_ref} a sosa:Procedure .

{obs_ref}
    a sosa:Observation ;
    sosa:madeBySensor {sensor_ref} ;
    sosa:usedProcedure {procedure_ref} ;
    sosa:observedProperty {property_ref} ;
    sosa:hasFeatureOfInterest {feature_ref} ;
    sosa:resultTime {self._datetime_literal(observation.phenomenon_time)} ;
    sosa:phenomenonTime [
        a time:Instant ;
        time:inXSDDateTimeStamp {self._datetime_stamp_literal(observation.phenomenon_time)}
    ] ;
{result_block}
"""

    def _ph(self, value: Any) -> str:
        return f"ph:{self._slug(value)}"

    def _slug(self, value: Any) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"[^a-zA-Z0-9_-]+", "-", text)
        return text.strip("-") or "unknown"

    def _enum_value(self, value: Any) -> str:
        if isinstance(value, Enum):
            return str(value.value)
        return str(value)

    def _datetime_literal(self, value: datetime) -> str:
        return f'"{self._datetime_value(value)}"^^xsd:dateTime'

    def _datetime_stamp_literal(self, value: datetime) -> str:
        return f'"{self._datetime_value(value)}"^^xsd:dateTimeStamp'

    def _datetime_value(self, value: datetime) -> str:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.isoformat()

    def _value_literal(self, value: Any) -> str:
        if isinstance(value, bool):
            return f'"{str(value).lower()}"^^xsd:boolean'

        if isinstance(value, int):
            return f'"{value}"^^xsd:integer'

        if isinstance(value, float):
            return f'"{value}"^^xsd:decimal'

        if isinstance(value, (dict, list)):
            return self._literal(json.dumps(value, ensure_ascii=False))

        return self._literal(value)

    def _literal(self, value: Any) -> str:
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _result_block(self, observation, has_unit: bool) -> str:
        if not has_unit:
            return f"    sosa:hasSimpleResult {self._value_literal(observation.simple_result)} ."

        return f"""    sosa:hasResult [
        a qudt:QuantityValue ;
        qudt:value {observation.simple_result} ;
        qudt:hasUnit unit:{observation.unit}
    ] ."""

    def _has_unit(self, unit: Any) -> bool:
        if unit is None:
            return False

        unit = str(unit).strip()
        return unit != "" and unit.lower() != "unknown"
