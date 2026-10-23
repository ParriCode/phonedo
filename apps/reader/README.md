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

El servicio conecta `on_register_device(Device)` y `on_observation(Observation)`.
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
`random-simulation` identifica su origen. No lee hardware ni carga configuración
externa o Manager. Usa core, server y biblioteca estándar; HTTP requiere aiohttp.
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

## Verificación

```sh
python3 -m pytest tests/app_tests/test_reader*.py -q
```

Incluye aislamiento del core/servicio, distribución de objetos, JSON Python/C++,
compilación C++ sin SDK Arduino, lifecycle HTTP, autenticación, SSE, colas y el
ciclo de vida del ejemplo Linux. Los tests de los adaptadores Linux eliminados
(configuración, serie, BLE, métricas y Manager) se retiraron con esa funcionalidad.
