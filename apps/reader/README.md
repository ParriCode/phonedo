# Phonendo Reader

Bibliotecas de dominio y servidor, con ejemplos separados por plataforma.

```text
apps/reader/
├── python/
│   ├── core/reader_core/
│   └── server/reader_server/
│       ├── __init__.py
│       ├── server.py
│       ├── service.py
│       ├── stream.py
│       └── serialization.py
├── cpp/
│   ├── core/                 # include/, src/, library.json
│   └── server/               # include/, src/, library.json
└── examples/
    ├── linux/                # Temperaturas simuladas y HTTP/SSE
    └── arduino/              # ESP8266: PIR, WiFi y entrega al Manager
```

## Responsabilidades

- **Core:** `ReaderCore`, `Device`, `Sensor` y `Observation`. Registra modelos,
  valida identidades y emite objetos del dominio. No importa servidor, HTTP ni hardware.
- **Service:** recibe un core externo y distribuye objetos a cero o más outputs.
  `ObservationOutput` se define junto al servicio Python. La serialización queda fuera del core.
- **Server Python:** `ReaderServer` implementa directamente HTTP/SSE con aiohttp.
  `stream.py` gestiona suscriptores, colas limitadas y desconexiones; `serialization.py`
  convierte observaciones a JSON.
- **Examples:** componen las bibliotecas y aportan simulación o hardware.
  No forman parte del core ni son importados por las bibliotecas.

```text
Ejemplo → core.ingest(Observation) → callback → ReaderService → outputs
                                                  ├── StreamOutput → SSE (Python)
                                                  └── ManagerOutput (ejemplo Arduino)
HTTP → ReaderServer → ReaderService → ReaderCore
```

Las rutas HTTP consultan el servicio; no hay endpoint de ingestión HTTP.
El ciclo de la aplicación pertenece al ejemplo. Se ha retirado el runtime genérico,
que ya no tenía consumidores, junto con los contratos de fuentes y workers.

## Python

```python
from reader_core import ReaderCore
from reader_server import ReaderServer, ServerConfig

core = ReaderCore("reader-1")
server = ReaderServer(core, ServerConfig(enabled=True))
# Dentro de una función async:
await server.start()
# Producir observaciones con core.ingest(observation).
await server.stop()
```

El servicio conecta `on_observation(Observation)`.
Requiere un core sin callbacks previamente asignados. Puede utilizarse solo,
sin HTTP ni dependencias externas: `ReaderService(core, outputs=...)`.

El servidor mantiene `start()`, `stop()`, `status()` y `app`:

- `enabled=False`: no escucha, `running` permanece falso y acceder a `app` falla explícitamente.
- `stream_enabled=False`: no crea stream ni StreamOutput; las rutas de consulta siguen funcionando.
- Las llamadas repetidas a start antes del cierre y a stop son idempotentes.
- Lifecycle: crear → arrancar → parar → desechar. Para reiniciar, crear otra instancia.
- aiohttp se importa únicamente al habilitar HTTP.

Rutas: `/health`, `/metadata`, `/devices` y `/stream` (SSE opcional).
Si se configura `token`, todas requieren `Authorization: Bearer <token>`.

## Ejemplo Linux

```sh
python3 -m pip install -r apps/reader/examples/linux/requirements.txt
python3 apps/reader/examples/linux/main.py
curl -N http://127.0.0.1:3002/stream
```

Genera una temperatura **simulada** entre 20 y 30 °C cada segundo. El procedimiento
`random-simulation` identifica su origen. Con `"simulation": "pulse"` en `config.json` emite en su lugar
pulsaciones (`heart_rate`, `BPM`) entre 95 y 120; con `"coldchain"`, temperaturas de transporte (`simulated-cold-chain`) entre 2 y 8 °C; con `"demo"`, 32 lecturas de pulso y después 32 de cadena de frío, sin mezclarlas, y luego se queda en silencio (`{"sequence": ["pulse", "coldchain"], "readings": 32, "rounds": 1}` lo configura); un objeto (`{"min": 60, "max": 70}`) sobrescribe cualquier campo. No lee hardware. Puede enviar a Managers mediante `config.json`. Usa core, server y biblioteca estándar; HTTP requiere aiohttp.
Ctrl+C cierra el servidor.

## C++ y Arduino

```cpp
ReaderCore core("reader-1");
ReaderService service(core, {&output});
core.ingest(observation);
```

Core y outputs deben vivir más que ReaderService. El servicio gestiona exclusivamente
los callbacks del core durante su vida; no se deben asignar otros ni conectar varios
servicios al mismo core. Su destructor desconecta los callbacks para no dejar
referencias a un servicio destruido.

Las dos bibliotecas comparten modelo, composición con core externo y distribución
de observaciones. No son idénticas: Python usa excepciones para errores; C++ utiliza
bool y `getLastError()`, con outputs que pueden devolver false. C++ limita dispositivos
y sensores y representa valores/fechas como cadenas. Python permite valores JSON
nativos y datetime. La serialización coincide para datos equivalentes.

C++ ofrece una interfaz `ReaderServer` con start/poll/stop; todavía no implementa
HTTP/SSE. Arduino usa setup/loop y envía al Manager mediante su adaptador de ejemplo.

```sh
pio run -d apps/reader/examples/arduino
```

El ejemplo está configurado para ESP8266 ESP-12E. Las dependencias PlatformIO apuntan
a `../../cpp/core` y `../../cpp/server`.

## Wear OS

[`examples/wearos`](examples/wearos/README.md) es una app para el OnePlus Watch 3
(Wear OS 5) que mide el pulso con Health Services y lo publica como `heart-rate`
en `bpm`. C++ (NDK + JNI) hace todo lo del Reader con `cpp/core` y `cpp/server`,
compilados desde aquí sin copiarlos; Kotlin pone el servidor HTTP/SSE del reloj
(mismo contrato que Python y el ESP32) y el envío a `<manager>/newEvent`. El
entorno entero (JDK, Gradle, SDK, NDK, CMake, emulador Wear OS) lo levanta devenv:

```sh
cd apps/reader/examples/wearos
cp secrets.example.properties secrets.properties
devenv shell -- build
```

## Verificación

Desde la raíz, con el entorno de pruebas del [README principal](../../README.md).

```sh
./tools/test.sh 'test_reader*.py'
./tools/test_integration.sh
```

Incluye aislamiento del core/servicio, distribución de objetos, JSON Python/C++,
compilación C++ sin SDK Arduino, lifecycle HTTP, autenticación, SSE, colas y el
ciclo de vida del ejemplo Linux. Los tests de los adaptadores Linux eliminados
(configuración, serie, BLE, métricas y Manager) se retiraron con esa funcionalidad.

## Varios Managers

`ManagerOutput` admite múltiples destinos HTTP en `services.managers` del JSON:

```json
{"services": {"managers": [
  {"url": "http://manager-a:3003", "token": "token-a"},
  {"url": "http://manager-b:3003", "token": "token-b"}
]}, "httpTimeoutSeconds": 10}
```

El ejemplo Linux carga `apps/reader/config.json` o `READER_CONFIG_PATH`.
Para otras composiciones: `ManagerOutput.from_config(path)` se pasa en `outputs`
a `ReaderServer`. Entrega
observaciones por `/newEvent` a cada destino; un error no impide intentar los demás.
No hay cola persistente de entrega en este output. El SSE admite múltiples Managers
suscritos y no espera confirmaciones. El ejemplo Arduino mantiene su adaptador C++;
puede componer varios `ManagerOutput`, uno por cliente Manager.

El JSON del ejemplo Linux también admite `readerId` y `server` con las opciones
de `ServerConfig` (`enabled`, `host`, `port`, `token`, `stream_enabled`, `queue_size`).

## Docker

Desde la raíz del proyecto:

```sh
docker build -t phonendo-reader apps/reader
```

[Arranque conjunto, configuración y pruebas](../../deploy/docker/README.md).

En el JSON, `stream.enabled` controla el `/stream` del Reader. El campo
`server` configura la escucha HTTP; el parámetro Python `ServerConfig.stream_enabled`
sigue disponible para composiciones por código. `services.managers` sigue siendo
la lista de destinos HTTP, no una suscripción.
