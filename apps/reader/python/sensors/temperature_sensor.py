# temperature_sensor.py

from datetime import datetime
from typing import Any, Optional

from apps.reader.python.reader_core.observation import Observation
from apps.reader.python.reader_core.sensor_base import PeriodicSensor, RawSensorAdapter


class TemperatureSensor(PeriodicSensor):
    """
    Sensor concreto para medir temperatura.

    Esta clase hereda de PeriodicSensor porque normalmente la temperatura
    se lee cada cierto intervalo de tiempo.

    Responsabilidades:
    - Recibir un valor bruto desde un adaptador o desde el Reader.
    - Convertir ese valor a float.
    - Validar que esté dentro de un rango permitido.
    - Crear una Observation semántica con la propiedad TEMPERATURE.
    """

    def __init__(
        self,
        feature_of_interest: str,
        interval_seconds: int,
        sensor_id: Optional[str] = None,
        procedure: str = "temperature-measurement",
        unit: str = "CELSIUS",
        min_value: float = -20.0,
        max_value: float = 80.0,
        raw_adapter: Optional[RawSensorAdapter] = None,
    ) -> None:
        """
        Inicializa un sensor de temperatura.

        feature_of_interest:
            Entidad sobre la que se mide la temperatura.
            Ejemplo: "patient-001", "body", "room", "wearable-user".

        interval_seconds:
            Cada cuántos segundos debe leerse el sensor.

        sensor_id:
            Identificador opcional del sensor.

        procedure:
            Procedimiento usado para obtener la medición.

        unit:
            Unidad de medida. Por defecto, CELSIUS.

        min_value y max_value:
            Rango válido de temperatura. Sirve para detectar valores corruptos,
            imposibles o fuera del dominio esperado.

        raw_adapter:
            Adaptador opcional para leer la temperatura desde una fuente real.
        """

        super().__init__(
            sensor_id=sensor_id,
            observable_property="Temperature",
            procedure=procedure,
            feature_of_interest=feature_of_interest,
            interval_seconds=interval_seconds,
            raw_adapter=raw_adapter,
        )

        if not unit:
            raise ValueError("unit no puede estar vacío")

        if min_value >= max_value:
            raise ValueError("min_value debe ser menor que max_value")

        self.unit = unit
        self.min_value = min_value
        self.max_value = max_value

    def build_observation(
        self,
        raw_value: Any,
        phenomenon_time: Optional[datetime] = None,
    ) -> Observation:
        """
        Construye una Observation a partir de un valor bruto de temperatura.

        raw_value puede ser:
        - int: 36
        - float: 36.5
        - str: "36.5"
        - dict: {"value": 36.5}
        - dict: {"temperature": 36.5}

        El resultado se guarda como un diccionario para no perder la unidad:

        {
            "value": 36.5,
            "unit": "CELSIUS"
        }
        """

        temperature = self._parse_temperature(raw_value)

        self._validate_temperature(temperature)

        simple_result = {
            "value": temperature,
            "unit": self.unit,
        }

        return self.addObservation(
            _simple_result=simple_result,
            _phenomenom_time=phenomenon_time,
        )

    def _parse_temperature(self, raw_value: Any) -> float:
        """
        Convierte el valor bruto recibido a float.

        Esta función concentra la lógica de interpretación del dato bruto.
        """

        if raw_value is None:
            raise ValueError("raw_value no puede ser None")

        if isinstance(raw_value, dict):
            if "value" in raw_value:
                raw_value = raw_value["value"]
            elif "temperature" in raw_value:
                raw_value = raw_value["temperature"]
            else:
                raise ValueError(
                    "raw_value como dict debe contener 'value' o 'temperature'"
                )

        try:
            return float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"No se puede convertir raw_value a temperatura: {raw_value}"
            ) from exc

    def _validate_temperature(self, temperature: float) -> None:
        """
        Valida que la temperatura esté dentro del rango permitido.
        """

        if temperature < self.min_value or temperature > self.max_value:
            raise ValueError(
                f"Temperatura fuera de rango: {temperature} {self.unit}. "
                f"Rango permitido: {self.min_value} - {self.max_value} {self.unit}"
            )
