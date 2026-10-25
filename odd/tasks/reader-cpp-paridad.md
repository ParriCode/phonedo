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
- [ ] T1 Payload con paridad: valor de `simple_result` tipado (número, bool,
  cadena, null, JSON crudo), hora ISO UTC, `unit` null si vacía, y
  `observationEventToJson` con el sobre. Ruta: delegada (2+ ficheros no
  triviales).
- [ ] T2 `ReaderService`: rechazar core con callback previo, `metadataJson`,
  `devicesJson`, `deviceJson` (`schemaVersion phonendo.device.v1`). Ruta:
  delegada.
- [ ] T3 Stream portable: suscriptores con cola acotada, desconexión del lento,
  `close()`, y helpers de formato SSE (`: connected`, `: heartbeat`,
  `event: observation`, `event: stream_closed`). Ruta: delegada.
- [ ] T4 Ejemplo ESP32 (`examples/esp32`): `platformio.ini` (esp32dev),
  servidor `/health`, `/metadata`, `/devices`, `/devices/{id}`, `/stream` con
  bearer opcional; `ManagerOutput` a varios Managers con `HTTPClient`;
  credenciales en `secrets.h` ignorado; temperatura simulada 20–30 °C como el
  ejemplo Linux. Ruta: delegada.
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

## Siguiente paso
T1.
