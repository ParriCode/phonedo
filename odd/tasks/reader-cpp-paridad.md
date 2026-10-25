# Reader C++: paridad con Python y ejemplo ESP32

## Objetivo
Poner `apps/reader/cpp` al nivel funcional del Reader Python y que un ESP32
pueda servir el mismo contrato HTTP/SSE y enviar observaciones a los Managers.

## Problema
El C++ solo tiene core, servicio y `observationToJson` (todo como cadena).
Le faltan: tipos JSON nativos y hora ISO UTC en el payload, el sobre del evento,
`metadata`/`devices`/`device`, el reparto de stream con colas acotadas, el
formato SSE, y un adaptador de plataforma con servidor y cliente HTTP.

## Restricciones
- **Python es solo lectura**: no se toca `apps/reader/python`, `examples/linux`
  ni las herramientas/tests Python existentes. Es la especificación.
- El contrato que ve el Manager no cambia: `/metadata` con
  `capabilities.stream: true`, SSE `event: observation` con el sobre
  `{eventType, readerId, deviceId, payloadFormat, payload}`, heartbeat < 30 s,
  `stream_closed`; `/newEvent` con `token` en el body.
- Plataforma objetivo del adaptador: **ESP32** (Arduino-ESP32 vía PlatformIO:
  `WiFi.h`, `HTTPClient`, `WebServer`). El núcleo sigue siendo portable y se
  prueba en el host con g++.
- `AGENTS.md`: sin commits salvo que el humano lo pida, sin atribución a IA,
  comentarios en castellano, cambios pequeños, no borrar tests.
- Credenciales WiFi/token fuera de git.

## Alcance autorizado
`apps/reader/cpp/**`, `apps/reader/examples/esp32/**` (nuevo),
`apps/reader/examples/arduino/**` solo si un cambio de API lo exige,
sección C++ de `apps/reader/README.md`, tests nuevos en `tests/app_tests/`.

## Tareas
- [x] T1 Payload con paridad: valor de `simple_result` tipado (número, bool,
  cadena, null, JSON crudo), hora ISO UTC, `unit` null si vacía, y
  `observationEventToJson` con el sobre. Ruta: delegada (2+ ficheros no
  triviales).
- [x] T2 `ReaderService`: rechazar core con callback previo, `metadataJson`,
  `devicesJson`, `deviceJson` (`schemaVersion phonendo.device.v1`). Ruta:
  delegada.
- [x] T3 Stream portable: suscriptores con cola acotada, desconexión del lento,
  `close()`, y helpers de formato SSE (`: connected`, `: heartbeat`,
  `event: observation`, `event: stream_closed`). Ruta: delegada.
- [x] T4 Ejemplo ESP32 (`examples/esp32`): `platformio.ini` con `esp32dev`
  (por defecto) y `esp32-s3-devkitc-1`; servidor `/health`, `/metadata`,
  `/devices`, `/devices/{id}`, `/stream` con bearer opcional; mDNS
  `phonendo-reader.local`; `ManagerOutput` a varios Managers con `HTTPClient`;
  credenciales en `secrets.h` ignorado (`#error` si falta). Datos (cambios
  del usuario, sustituyen la temperatura simulada): un dispositivo
  `esp32-device` con `sensor-1` (entero aleatorio 0–100 cada segundo,
  `random-value`/`random-simulation`), `sensor-2` (valor 2 por pulsación del
  botón en `BUTTON_PIN`, GPIO 4 por defecto, `INPUT_PULLUP`, antirrebote
  50 ms sin `delay()`, `button-press`), `sensor-3` (HC-SR04, cm con un
  decimal o null sin eco, `distance`/`ultrasonic-hcsr04`, unit `cm`, mide
  cada 100 ms, envía con cambio ≥ 2 cm o null↔número, máx. 5/s; Trig/Echo
  ESP32 26/27, S3 6/7) y `sensor-4` (KY-040, `{"position","pressed"}`,
  `rotary-encoder`/`encoder-ky040`, cuadratura por interrupciones con tabla
  de estados y 4 transiciones por muesca, máx. 10/s; CLK/DT/SW ESP32
  25/33/32, S3 15/16/17). Pines configurables en `secrets.h`. El joystick
  se retiró. Ruta: delegada.
- [ ] T5 README del Reader: sección C++ y ESP32.

## Comprobaciones
- Tests C++ en host (g++ `-std=c++17 -Wall -Wextra -Werror`) para T1–T3, con
  RED antes de implementar.
- Tests existentes del Reader en verde: `./tools/test.sh 'test_reader*.py'`.
- `pio run -d apps/reader/examples/arduino` (ESP8266) y
  `pio run -d apps/reader/examples/esp32` compilan.

## Entrega
Sin commits por `AGENTS.md`; el humano decide cuándo. Previsión: > 400 líneas.

## Progreso
- Exploración hecha (2026-10-25). Espejo Engram: **pendiente** (Engram no
  disponible en esta sesión).

- T1–T3 (ruta: delegada, un único escritor; disparador: 2+ ficheros no
  triviales en core y server). Cambios aditivos: el constructor de cadenas de
  `Observation` y `simpleResult` siguen igual, así que el ejemplo ESP8266 y
  los tests existentes compilan sin tocarlos.
  - API nueva: `ResultType` + `setText/setInteger/setNumber/setBoolean/
    setNull/setRawJson`; `isoUtcFromEpochMillis/Micros`,
    `normalizePhenomenonTime`; `observationEventToJson`, `jsonString`,
    `jsonStringOrNull`; `Device::creationDatetime`;
    `ReaderCore::hasOnObservationCallback`; `ReaderService::isAttached/
    getLastError/metadataJson/devicesJson/deviceJson`; `reader_stream.h`
    (`ObservationStream`, `StreamPoll`, `StreamOutput`, `sse*`,
    `PHONENDO_SSE_HEARTBEAT_MS`).
  - Divergencias con Python: `device()` de Python lee un `creation_datetime`
    que no existe (500); C++ emite `creationDatetime` null si está vacío. El
    JSON de C++ va sin espacios y con UTF-8 sin escapar (mismo contenido).
    `setNumber` con NaN/inf emite null (Python emitiría `NaN`, JSON inválido).
    Un `ReaderService` con core ya enganchado no lanza: queda sin enganchar.
  - Evidencia RED: `test_reader_cpp_parity.py` 17 fallos por API inexistente
    (`setInteger`, `isoUtcFromEpochMillis`… no declarados).
  - Evidencia GREEN: `./tools/test.sh 'test_reader*.py'` → 46 passed (29
    previos + 17 nuevos). `.venv` creado en local para poder ejecutarlo.
  - `pio run -d apps/reader/examples/arduino`: SUCCESS sobre un export de HEAD
    (e36c46f, mismas librerías `cpp/` que el árbol). El directorio
    `examples/arduino` apareció borrado del árbol de trabajo durante la sesión
    (no por el escritor); el usuario aprobó dejarlo así y omitir esta
    comprobación. Quedan referencias en `AGENTS.md:97` y
    `apps/reader/README.md:110`.
- T4 (ruta: delegada, mismo escritor). Ficheros nuevos en
  `apps/reader/examples/esp32/`: `platformio.ini`, `.gitignore`, `README.md`,
  `src/{main.cpp, reader_http.{h,cpp}, manager_output.{h,cpp},
  secrets.example.h}`. Sin cambios en `cpp/`.
  - `pio run -d apps/reader/examples/esp32 -e esp32dev`: SUCCESS (RAM 17,5 %,
    flash 47,0 % de 3 MB). Primero falló por tamaño (112,7 % de 1,3 MB):
    se añadió `board_build.partitions = huge_app.csv`.
  - `pio run -d apps/reader/examples/esp32 -e esp32-s3-devkitc-1`: SUCCESS
    (RAM 16,7 %, flash 45,2 %).
  - Sin `secrets.h`: falla con el `#error` que pide copiar el ejemplo.
    El `secrets.h` temporal se borró tras cada compilación.
  - `./tools/test.sh 'test_reader*.py'`: 46 passed.
  - SSE: comprobado en el WebServer instalado (arduino-esp32 3.x) que suelta
    el cliente por asignación (`shared_ptr`), no con `stop()`, así que la copia
    guardada mantiene el socket. Sin prueba en placa todavía.
  - Límites: 4 suscriptores SSE, cola de 16 por suscriptor; un Manager que no
    responde bloquea el bucle hasta 5 s; antes de NTP la hora sale en 1970.

- T4, cambio 2 (aleatorio + joystick): solo `main.cpp`,
  `secrets.example.h` y `README.md` del ejemplo; sin cambios en `cpp/`.
  `pio run … -e esp32dev`: SUCCESS (RAM 17,6 %, flash 47,4 %);
  `-e esp32-s3-devkitc-1`: SUCCESS (RAM 16,8 %, flash 45,7 %), ambos con
  `secrets.h` temporal ya borrado. Sin prueba en placa.

- T4, cambio 3 (sin joystick; HC-SR04 + KY-040): `main.cpp`,
  `secrets.example.h` y `README.md` del ejemplo; sin cambios en `cpp/`.
  `pio run … -e esp32dev`: SUCCESS (RAM 17,8 %, flash 47,3 %);
  `-e esp32-s3-devkitc-1`: SUCCESS (RAM 17,1 %, flash 46,3 %), con
  `secrets.h` temporal ya borrado. Sin prueba en placa.

## Siguiente paso
Probar en placa con curl (README del ejemplo). T5.
