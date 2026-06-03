# Phonendo Python Reader

Este módulo implementa el Reader Python de Phonendo. Su responsabilidad es recibir datos crudos desde fuentes externas, asociarlos a un dispositivo y sensor conocidos, construir una observación semántica y enviarla al Manager.

El Reader actual está pensado para trabajar principalmente con sensores Bluetooth/RFCOMM, BLE o puertos serie. Puede usar una configuración previa en `devices_and_sensors.json`, pero también acepta sensores no configurados aplicando políticas de fallback.

## Estructura

```text
apps/reader/python/
├── main.py
├── devices_and_sensors.json
├── bluetooth_manager/
│   ├── __init__.py
│   └── bluetooth_manager.py
└── reader_core/
    ├── core.py
    ├── device.py
    ├── observation.py
    ├── sensor.py
    └── serializer.py
```

## Flujo General

1. `Reader` carga variables de entorno desde `config.env`.
2. `Reader` crea un `ReaderCore`.
3. `Reader` carga `devices_and_sensors.json` si existe.
4. `Reader.factory()` crea los `Device` y `Sensor` definidos en configuración.
5. `BluetoothDeviceManager` escucha datos Bluetooth/RFCOMM.
6. Cada dato recibido llega a `Reader.handle_bluetooth_data()`.
7. El Reader busca el `Device` y `Sensor`.
8. `ReaderCore.ingest_raw_measurement()` crea una `Observation`.
9. `SosaTTLSerializer` convierte la observación a Turtle/SOSA.
10. `ManagerClient` envía la observación al Manager por HTTP.

## Configuración De Dispositivos Y Sensores

El archivo `devices_and_sensors.json` define qué dispositivos y sensores conoce el Reader antes de empezar a recibir datos.

Ejemplo actual:

```json
{
  "bluetooth": {
    "transports": ["RFCOMM"],
    "rfcomm": {
      "baudrate": 9600
    }
  },
  "devices": [
    {
      "comm": "/dev/rfcomm0",
      "mac": "00:21:13:01:1F:91",
      "device_id": "prueba1",
      "allow_conflicts": false
    }
  ],
  "sensors": [
    {
      "sensor_id": "temp1",
      "procedure": "termorreceptor",
      "observable_property": "temperatura",
      "device_id": "prueba1",
      "allow_conflicts": false
    }
  ]
}
```

La sección `bluetooth` es opcional. Permite configurar transports y parámetros del `BluetoothDeviceManager`:

- `transports`: lista con `"RFCOMM"`, `"BLE"` o ambos.
- `rfcomm.baudrate`: velocidad de lectura de los puertos RFCOMM.
- `rfcomm.ports`: lista opcional de puertos permitidos.
- `rfcomm.devices`: metadatos manuales por puerto.
- `ble.scan_timeout_seconds`: tiempo de escaneo BLE.
- `ble.sleep_seconds`: pausa entre escaneos BLE.

Campos de `devices`:

- `device_id`: identificador lógico del dispositivo dentro de Phonendo.
- `mac`: MAC real, MAC configurada o MAC pseudónima del dispositivo.
- `device_type`: tipo de dispositivo. Si no se indica, se usa `"bluetooth"`.
- `platform`: plataforma opcional.
- `comm`: fuente de comunicación local, por ejemplo `/dev/rfcomm0`.
- `allow_conflicts`: si es `false`, se descartan mensajes que contradigan la identidad configurada del dispositivo.

Campos de `sensors`:

- `sensor_id`: identificador del sensor dentro del dispositivo.
- `device_id`: dispositivo al que pertenece el sensor.
- `observable_property`: propiedad observada, por ejemplo `"temperatura"`.
- `procedure`: procedimiento de medición.
- `feature_of_interest`: entidad observada. Si no se indica, se usa `"unknown-feature"`.
- `unit`: unidad opcional, por ejemplo `"CELSIUS"`.
- `allow_conflicts`: si es `false`, se descartan mensajes que contradigan el sensor o su semántica configurada.

## Clases Principales

### Reader

Definida en `main.py`.

Es la clase de orquestación del Reader. Carga configuración, mantiene el registro local de dispositivos y sensores, recibe datos Bluetooth y delega el procesamiento semántico en `ReaderCore`.

Atributos principales:

- `env`: variables leídas desde `config.env`.
- `core`: instancia de `ReaderCore`.
- `devices`: diccionario `device_id -> Device`.
- `sensors`: diccionario `sensor_id -> Sensor`.
- `mac`: MAC del Reader o MAC fallback.
- `reader_id`: identificador del Reader.
- `config_file`: archivo de configuración usado para dispositivos y sensores.

Métodos:

- `get_manager_url()`: resuelve la URL base del Manager.
- `start()`: arranca el `BluetoothDeviceManager`.
- `handle_bluetooth_data(observation)`: recibe una `BluetoothObservation`, crea fallback si no existe device/sensor, e ingiere la medición.
- `resolve_observation_device(observation)`: decide qué `device_id` y MAC usar para una observación.
- `factory(config)`: crea dispositivos y sensores desde el JSON de configuración.
- `bluetooth_manager_from_config(config)`: construye el manager Bluetooth desde configuración.
- `device_from_json(json_data)`: construye un `Device`.
- `sensor_from_json(json_data)`: construye un `Sensor`.
- `load_config(path)`: lee un archivo JSON de configuración.
- `resolve_reader_mac(mac, mac_policy)`: resuelve la MAC del Reader por argumento, sistema, aleatoria local o fallback.
- `load_env(path)`: lee un archivo `.env` simple.

### BluetoothDeviceManager

Definida en `bluetooth_manager/bluetooth_manager.py`.

Gestiona la lectura de datos Bluetooth. Actualmente soporta:

- `BLE`: escaneo de advertisements BLE.
- `RFCOMM`: lectura de puertos serie `/dev/rfcomm*`.

Produce objetos `BluetoothObservation`.

Formatos RFCOMM soportados:

```json
{
  "macAddress": "AA:BB:CC:DD:EE:FF",
  "deviceId": "device-1",
  "sensorId": "temp1",
  "value": "24.5",
  "observableProperty": "temperatura",
  "unit": "CELSIUS"
}
```

```text
temp1:24.5
```

```text
24.5
```

Si el mensaje no incluye `sensor_id`, se usa el sensor configurado para el puerto o el propio nombre del puerto.

### BluetoothObservation

Representa una medición recibida por Bluetooth.

Campos:

- `mac`: MAC asociada al dispositivo remoto. Puede venir de configuración.
- `sensor_id`: sensor que produjo el dato.
- `value`: valor recibido.
- `transport`: `"BLE"` o `"RFCOMM"`.
- `observation_property`: propiedad observada si el origen la indica.
- `device_id`: identificador lógico del dispositivo si el origen lo indica.
- `device_type`: tipo de dispositivo si el origen lo indica.
- `procedure`: procedimiento de medición si el origen lo indica.
- `feature_of_interest`: entidad observada si el origen lo indica.
- `unit`: unidad si el origen la indica.
- `source`: fuente local, por ejemplo `/dev/rfcomm0`.

### ReaderCore

Definida en `reader_core/core.py`.

Contiene la lógica principal de registro, ingestión y envío de observaciones.

Atributos:

- `reader_id`: identificador del Reader.
- `devices`: dispositivos registrados en memoria.
- `serializer`: instancia de `SosaTTLSerializer`.
- `manager_client`: cliente HTTP para comunicarse con el Manager.

Métodos:

- `register_device(device)`: registra un dispositivo localmente y en el Manager.
- `add_device(device)`: registra un dispositivo solo en memoria.
- `remove_device(device_id)`: elimina un dispositivo local.
- `get_device(device_id)`: recupera un dispositivo.
- `ingest_raw_measurement(device_id, sensor_id, raw_value, phenomenon_time, send)`: transforma un valor crudo en observación.
- `send_observation(observation)`: serializa y envía una observación.

### ManagerClient

Definida en `reader_core/core.py`.

Encapsula las llamadas HTTP al Manager.

Métodos:

- `register_device(reader_id, device)`: envía `/registerDevice`.
- `send_observation_ttl(ttl, reader_id, device_id)`: envía `/newEvent`.

### Device

Definida en `reader_core/device.py`.

Representa una fuente física o lógica de datos. Un `Device` aloja uno o más sensores.

Atributos:

- `device_id`
- `device_type`
- `mac_address`
- `platform`
- `_sensors`

Métodos:

- `add_sensor(sensor)`
- `get_sensor(sensor_id)`
- `remove_sensor(sensor_id)`
- `list_sensors()`
- `has_sensor(sensor_id)`
- `sensor_count()`

### Sensor

Definida en `reader_core/sensor.py`.

Representa un sensor lógico dentro de un dispositivo.

Atributos:

- `sensor_id`
- `observable_property`
- `procedure`
- `feature_of_interest`
- `unit`
- `device_id`

Métodos:

- `build_observation(raw_value, phenomenon_time)`: crea una observación a partir de un valor crudo.
- `addObservation(_simple_result, _phenomenom_time)`: alias compatible de `build_observation`.

Actualmente `Sensor` no aplica validación específica al valor recibido. Solo lo encapsula en una observación usando la configuración disponible.

### Observation

Definida en `reader_core/observation.py`.

Representa una observación generada por un sensor.

Campos:

- `observable_property`
- `simple_result`
- `phenomenon_time`
- `feature_of_interest`
- `procedure`
- `device_id`
- `sensor_id`
- `unit`
- `observation_id`

Métodos:

- `to_dict()`: devuelve una representación JSON simple.

### SosaTTLSerializer

Definida en `reader_core/serializer.py`.

Convierte una `Observation` en RDF/Turtle usando SOSA.

Genera recursos para:

- `sosa:Platform`
- `sosa:Sensor`
- `sosa:ObservableProperty`
- `sosa:FeatureOfInterest`
- `sosa:Procedure`
- `sosa:Observation`

## Diagrama De Clases

```mermaid
classDiagram
    class Reader {
        +env: dict
        +core: ReaderCore
        +devices: dict
        +sensors: dict
        +mac: str
        +reader_id: str
        +get_manager_url() str
        +handle_bluetooth_data(observation) void
        +factory(config) void
        +device_from_json(json_data) Device
        +sensor_from_json(json_data) Sensor
        +load_config(path) dict
        +load_env(path) dict
    }

    class BluetoothDeviceManager {
        +on_measurement
        +transports: set
        +start() async
        +stop() async
        +parse_ble_advertisement(mac, adv) list
        +parse_rfcomm_message(port, raw) list
    }

    class BluetoothObservation {
        +mac: str
        +sensor_id: str
        +value: str
        +transport: str
        +observation_property: str
        +source: str
    }

    class ReaderCore {
        +reader_id: str
        +devices: dict
        +serializer: SosaTTLSerializer
        +manager_client: ManagerClient
        +register_device(device) void
        +add_device(device) void
        +remove_device(device_id) void
        +get_device(device_id) Device
        +ingest_raw_measurement(device_id, sensor_id, raw_value, phenomenon_time, send) Observation
        +send_observation(observation) void
    }

    class ManagerClient {
        +base_url: str
        +token: str
        +register_device(reader_id, device) void
        +send_observation_ttl(ttl, reader_id, device_id) void
    }

    class Device {
        +device_id: str
        +device_type: str
        +mac_address: str
        +platform: str
        +add_sensor(sensor) void
        +get_sensor(sensor_id) Sensor
        +remove_sensor(sensor_id) void
        +list_sensors() list
    }

    class Sensor {
        +sensor_id: str
        +observable_property: str
        +procedure: str
        +feature_of_interest: str
        +unit: str
        +device_id: str
        +build_observation(raw_value, time) Observation
        +addObservation(result, time) Observation
    }

    class Observation {
        +observable_property: str
        +simple_result
        +phenomenon_time
        +feature_of_interest: str
        +procedure: str
        +device_id: str
        +sensor_id: str
        +unit: str
        +observation_id: str
        +to_dict() dict
    }

    class SosaTTLSerializer {
        +serialize(observation) str
    }

    Reader --> ReaderCore
    Reader --> BluetoothDeviceManager
    BluetoothDeviceManager --> BluetoothObservation
    ReaderCore --> Device
    ReaderCore --> ManagerClient
    ReaderCore --> SosaTTLSerializer
    Device "1" o-- "*" Sensor
    Sensor --> Observation
    SosaTTLSerializer --> Observation
```

## Diagrama De Estados Del Reader

```mermaid
stateDiagram-v2
    [*] --> Starting

    Starting --> LoadingEnv: load_env()
    LoadingEnv --> CreatingCore: ReaderCore()
    CreatingCore --> LoadingConfig: load_config()
    LoadingConfig --> BuildingFactory: factory()
    BuildingFactory --> StartingBluetooth: BluetoothDeviceManager()
    StartingBluetooth --> Listening: start()

    Listening --> ReceivingData: BluetoothObservation
    ReceivingData --> ResolveDevice: mac/device_id
    ResolveDevice --> CreateFallbackDevice: device not found
    ResolveDevice --> ResolveSensor: device found
    CreateFallbackDevice --> ResolveSensor

    ResolveSensor --> CreateFallbackSensor: sensor not found
    ResolveSensor --> IngestMeasurement: sensor found
    CreateFallbackSensor --> IngestMeasurement

    IngestMeasurement --> BuildObservation: Sensor.build_observation()
    BuildObservation --> SerializeTTL: SosaTTLSerializer.serialize()
    SerializeTTL --> SendManager: ManagerClient.send_observation_ttl()
    SendManager --> Listening

    Listening --> Error: read/parse/http error
    Error --> Listening: retry/reconnect
```

## Diagrama De Secuencia De Una Medición RFCOMM

```mermaid
sequenceDiagram
    participant Port as /dev/rfcomm0
    participant BTM as BluetoothDeviceManager
    participant Reader
    participant Core as ReaderCore
    participant Device
    participant Sensor
    participant Serializer as SosaTTLSerializer
    participant Manager as Manager

    Port->>BTM: bytes
    BTM->>BTM: parse_rfcomm_message()
    BTM->>Reader: BluetoothObservation
    Reader->>Reader: resolve device_id and sensor_id
    Reader->>Core: ingest_raw_measurement()
    Core->>Device: get_sensor(sensor_id)
    Device-->>Core: Sensor
    Core->>Sensor: build_observation(raw_value)
    Sensor-->>Core: Observation
    Core->>Serializer: serialize(observation)
    Serializer-->>Core: Turtle/SOSA
    Core->>Manager: POST /newEvent
```

## Políticas Actuales

### Dispositivo configurado

Si el dispositivo existe en `devices_and_sensors.json`, se crea al arrancar y se registra localmente.

### Sensor configurado

Si el sensor existe en `devices_and_sensors.json`, se crea al arrancar y se enlaza con su `Device`.

### Dispositivo no configurado

Si llega una observación de un dispositivo no registrado, `handle_bluetooth_data()` crea un `Device` básico. Si el mensaje trae `device_id`, se usa ese identificador. Si no lo trae, se usa la MAC observada.

```text
device_id = observation.device_id or observation.mac
device_type = observation.device_type or bluetooth
mac_address = observation.mac
```

Si `observation.mac == "unknown"` o no hay MAC, el dato se considera originado por el propio Reader:

```text
device_id = reader_id
mac_address = reader.mac
```

### Sensor no configurado

Si llega un `sensor_id` no registrado, se crea un `Sensor` básico:

```text
observable_property = observation.observation_property or "unknown"
procedure = observation.procedure or "unknown"
feature_of_interest = observation.feature_of_interest or "unknown"
unit = observation.unit or "Unknown"
```

Este fallback permite no perder el dato, pero la calidad semántica es limitada.

### MAC del Reader

La MAC del Reader se resuelve con esta prioridad:

```text
--mac > --mac-policy random > --mac-policy default > bluetoothctl/uuid.getnode() > default
```

La MAC por defecto es local/pseudónima:

```text
02:22:22:22:22:22
```

## Limitaciones Actuales

El Reader actual cubre bien el caso:

```text
sensor simple + configuración previa
```

Todavía no cubre completamente:

- Handshake de autodescripción del dispositivo.
- Mensajes `hello` con lista de sensores.
- Persistencia de dispositivos descubiertos dinámicamente.
- Resolución automática fiable de MAC remota desde `/dev/rfcomm0`.
- Validación específica por tipo de sensor.
- Lectura activa desde un adaptador local por sensor.
- Diferenciación fuerte entre MAC física, MAC configurada y MAC pseudónima.

## Futuras Extensiones

Extensiones razonables:

- Soportar mensajes de autodescripción:

```json
{
  "type": "hello",
  "device_id": "arduino-01",
  "mac": "00:21:13:01:1F:91",
  "sensors": [
    {
      "sensor_id": "temp1",
      "observable_property": "temperatura",
      "procedure": "termorreceptor",
      "feature_of_interest": "patient-001",
      "unit": "CELSIUS"
    }
  ]
}
```

- Guardar explícitamente el origen de identidad:

```text
configured > handshake > transport_discovery > pseudonymous > unknown
```

- Guardar en cada device el origen de identidad:

```text
configured
handshake
transport
pseudonymous
fallback
```

- Permitir que un sensor desconocido quede en estado pendiente si no hay semántica suficiente.

## Ejecución

El entrypoint actual es:

```bash
python apps/reader/python/main.py
```

Opciones principales:

```bash
python apps/reader/python/main.py --config apps/reader/python/devices_and_sensors.json
python apps/reader/python/main.py --mac 02:aa:bb:cc:dd:ee
python apps/reader/python/main.py --mac-policy random
python apps/reader/python/main.py --reader-id reader-1
```

El arranque usa `asyncio.run(reader.start())`.

## Resumen

El Reader Python actual es una base configurable para recibir datos por Bluetooth/RFCOMM y BLE, asociarlos a dispositivos y sensores, construir observaciones y enviarlas al Manager. La configuración previa sigue siendo el mecanismo más fiable para dar semántica a sensores simples. Los sensores no configurados se aceptan mediante fallback, usando los metadatos disponibles y rellenando lo desconocido con valores `unknown`/`Unknown`.
