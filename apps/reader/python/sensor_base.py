from abc import ABC, abstractmethod
from datetime import datetime
from uuid import uuid4
from typing import Any, Optional, Protocol

from observation import Observation, ObservableProperty


class RawSensorAdapter(Protocol):
    """
    Interfaz común para cualquier adaptador que se encargue de leer datos
    directamente desde una fuente física o externa.

    Esta clase representa la capa más cercana al dispositivo real.

    Ejemplos de implementaciones posibles:
    - BluetoothSensorAdapter: lee datos desde un wearable por Bluetooth/BLE.
    - HttpSensorAdapter: lee datos desde un endpoint HTTP.
    - LocalSensorAdapter: lee datos desde un sensor local, fichero o puerto serie.

    El objetivo de esta interfaz es que SensorBase no dependa directamente
    de un protocolo concreto como Bluetooth, HTTP o lectura local.
    """

    def read_raw_value(self) -> Any:
        """
        Lee un valor bruto desde el dispositivo o fuente de datos.

        Devuelve Any porque el dato bruto puede tener muchos formatos:
        - un número: 85
        - un JSON
        - bytes recibidos por Bluetooth
        - una cadena de texto
        - una estructura propia del dispositivo

        Después, cada sensor concreto será responsable de transformar ese
        dato bruto en una Observation semántica.
        """
        ...


class SensorBase(ABC):
    """
    Clase base abstracta para todos los sensores del Reader.

    Esta clase contiene la información común que necesita cualquier sensor
    para generar observaciones compatibles con el modelo semántico del sistema.

    No representa necesariamente un sensor físico directamente, sino la
    abstracción lógica de un sensor dentro del Reader.

    Por ejemplo:
    - HeartRateSensor
    - TemperatureSensor
    - SpO2Sensor

    Cada sensor tiene asociada una propiedad observable, un procedimiento,
    una entidad observada y opcionalmente un adaptador de lectura de datos.
    """

    def __init__(
        self,
        observable_property: ObservableProperty,
        procedure: str,
        feature_of_interest: str,
        sensor_id: str | None = None,
        raw_adapter: Optional[RawSensorAdapter] = None,

        device_id: Optional[str] = None, 
    ) -> None:
        """
        Inicializa los campos comunes de cualquier sensor.

        observable_property:
            Propiedad que mide el sensor.
            Ejemplo: HEART_RATE, TEMPERATURE, SPO2.

        procedure:
            Procedimiento o mecanismo usado para obtener la medición.
            En SOSA/SSN puede representar el método, algoritmo o sensor
            que produce la observación.

        feature_of_interest:
            Entidad sobre la que se realiza la observación.
            Por ejemplo, el paciente, usuario, cuerpo o dispositivo observado.

        sensor_id:
            Identificador único del sensor. Si no se proporciona, se genera
            automáticamente con UUID.

        raw_adapter:
            Adaptador opcional usado para leer datos directamente desde una
            fuente externa. Es útil especialmente en sensores periódicos.
        """

        self.sensor_id = sensor_id or str(uuid4())
        self.observable_property = observable_property
        self.procedure = procedure
        self.feature_of_interest = feature_of_interest
        self.raw_adapter = raw_adapter

        self.device_id = device_id

    def addObservation(
        self,
        _simple_result: Any,
        _phenomenom_time: Optional[datetime] = None,
    ) -> Observation:
        """
        Crea una Observation a partir de un valor ya procesado.

        Este método se usa cuando ya se dispone del valor final que se quiere
        publicar como resultado simple de la observación.

        Por ejemplo:
        - simple_result = 85 para frecuencia cardíaca.
        - simple_result = 36.7 para temperatura.
        - simple_result = 98 para saturación de oxígeno.

        Si no se proporciona phenomenon_time, se usa la fecha y hora actual.

        Este método no interpreta datos brutos. Solo construye la observación
        usando los metadatos semánticos del sensor.
        """

        if not _phenomenom_time:
            _phenomenom_time = datetime.now()

        return Observation(
            observable_property=self.observable_property,
            simple_result=_simple_result,
            phenomenon_time=_phenomenom_time,
            feature_of_interest=self.feature_of_interest,
            procedure=self.procedure,
            sensor_id=self.sensor_id,
            device_id=self.device_id

        )

    @abstractmethod
    def build_observation(
        self,
        raw_value: Any,
        phenomenon_time: Optional[datetime] = None,
    ) -> Observation:
        """
        Método abstracto que debe implementar cada sensor concreto.

        Su responsabilidad es transformar un valor bruto recibido desde un
        adaptador, evento o dispositivo en una Observation válida.

        La diferencia con addObservation es importante:

        - build_observation recibe un dato bruto.
        - interpreta, valida o transforma ese dato.
        - después crea una Observation.

        Por ejemplo, un HeartRateSensor podría recibir bytes desde Bluetooth
        y convertirlos en un número entero de pulsaciones por minuto.

        Al ser abstractmethod, SensorBase no puede instanciarse directamente.
        Todas las clases hijas deben implementar este método.
        """
        pass


class EventDrivenSensor(SensorBase, ABC):
    """
    Clase base para sensores dirigidos por eventos.

    Un sensor dirigido por eventos no se consulta cada cierto tiempo.
    En lugar de eso, genera una observación cuando ocurre un evento externo.

    Ejemplos:
    - un wearable envía una notificación BLE cuando cambia el ritmo cardíaco;
    - un endpoint HTTP recibe un nuevo dato;
    - un sistema externo emite un evento de medición.

    Esta clase es útil para sensores que reaccionan a datos entrantes.
    """

    def __init__(
        self,
        sensor_id: str,
        observable_property: ObservableProperty,
        procedure: str,
        feature_of_interest: str,
        event_name: str,
        raw_adapter: Optional[RawSensorAdapter] = None,
    ) -> None:
        """
        Inicializa un sensor basado en eventos.

        event_name:
            Nombre del evento que este sensor sabe manejar.
            Por ejemplo: "heart_rate_changed" o "temperature_received".

        raw_adapter:
            Es opcional. En un sensor dirigido por eventos puede no ser
            necesario, porque el dato suele llegar directamente en el payload
            del evento.
        """

        super().__init__(
            sensor_id=sensor_id,
            observable_property=observable_property,
            procedure=procedure,
            feature_of_interest=feature_of_interest,
            raw_adapter=raw_adapter,
        )

        if not event_name:
            raise ValueError("event_name no puede estar vacío")

        self.event_name = event_name

    def handle_event(
        self,
        payload: Any,
        phenomenon_time: Optional[datetime] = None,
    ) -> Observation:
        """
        Procesa un evento recibido por el Reader.

        payload:
            Contenido del evento. Puede ser un número, JSON, bytes,
            diccionario, etc.

        Este método delega la interpretación real del dato en build_observation,
        porque cada sensor concreto sabe cómo transformar su payload en una
        Observation.

        Por ejemplo:
        - HeartRateSensor interpreta el payload como pulsaciones.
        - TemperatureSensor interpreta el payload como temperatura.
        """

        return self.build_observation(
            raw_value=payload,
            phenomenon_time=phenomenon_time,
        )


class PeriodicSensor(SensorBase, ABC):
    """
    Clase base para sensores periódicos.

    Un sensor periódico se consulta cada cierto intervalo de tiempo.
    Este tipo de sensor necesita normalmente un RawSensorAdapter, porque debe
    ir a leer activamente el valor desde una fuente externa.

    Ejemplos:
    - leer temperatura cada 10 segundos;
    - consultar frecuencia cardíaca cada 5 segundos;
    - leer un sensor local cada minuto.

    La clase controla cuándo debe hacerse una nueva lectura y actualiza el
    instante de la última consulta.
    """

    def __init__(
        self,
        observable_property: ObservableProperty,
        procedure: str,
        feature_of_interest: str,
        interval_seconds: int,
        sensor_id: Optional[str] = None,
        raw_adapter: Optional[RawSensorAdapter] = None,
    ) -> None:
        """
        Inicializa un sensor periódico.

        interval_seconds:
            Intervalo mínimo, en segundos, que debe pasar entre dos lecturas.

        raw_adapter:
            Adaptador que permite leer el dato bruto desde el dispositivo o
            fuente externa. En sensores periódicos suele ser necesario.

        last_poll_time:
            Guarda la última vez que se consultó el sensor.
            Al principio es None porque todavía no se ha hecho ninguna lectura.
        """

        super().__init__(
            sensor_id=sensor_id,
            observable_property=observable_property,
            procedure=procedure,
            feature_of_interest=feature_of_interest,
            raw_adapter=raw_adapter,
        )

        if interval_seconds <= 0:
            raise ValueError("interval_seconds debe ser mayor que 0")

        self.interval_seconds = interval_seconds
        self.last_poll_time: Optional[datetime] = None

    def should_poll(self, now: Optional[datetime] = None) -> bool:
        """
        Indica si ya ha pasado suficiente tiempo para volver a leer el sensor.

        Devuelve True cuando:
        - nunca se ha leído el sensor;
        - o ha pasado al menos interval_seconds desde la última lectura.

        Este método permite que el Reader decida si debe llamar a poll()
        sin hacer lecturas innecesarias.
        """

        now = now or datetime.now()

        if self.last_poll_time is None:
            return True

        elapsed = (now - self.last_poll_time).total_seconds()

        return elapsed >= self.interval_seconds

    def poll(self, now: Optional[datetime] = None) -> Observation:
        """
        Realiza una lectura activa del sensor.

        Flujo:
        1. Comprueba que existe un raw_adapter configurado.
        2. Lee el valor bruto mediante read_raw_value().
        3. Convierte ese valor bruto en una Observation usando build_observation().
        4. Actualiza last_poll_time.
        5. Devuelve la Observation generada.

        Este método representa el comportamiento típico de un sensor periódico:
        el Reader o un scheduler lo llama cada cierto tiempo para obtener una
        nueva medición.
        """

        if self.raw_adapter is None:
            raise RuntimeError(
                f"El sensor '{self.sensor_id}' no tiene raw_adapter configurado"
            )

        now = now or datetime.now()

        raw_value = self.raw_adapter.read_raw_value()

        observation = self.build_observation(
            raw_value=raw_value,
            phenomenon_time=now,
        )

        self.last_poll_time = now

        return observation