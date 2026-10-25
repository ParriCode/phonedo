# Reader Phonendo en ESP32

Ejemplo de plataforma para ESP32 (Arduino + PlatformIO). Usa el núcleo y el
servidor portables de `apps/reader/cpp` y sirve el mismo contrato que el
Reader Python: `/health`, `/metadata`, `/devices`, `/devices/{id}` y
`/stream` (SSE), y envía opcionalmente cada evento a uno o varios Managers
(`POST <url>/newEvent` con `token` en el cuerpo).

## Datos

Un dispositivo `esp32-device` (tipo `ESP32`) con cuatro sensores:

| Sensor | Cuándo emite | `simple_result` | `observable_property` | `procedure` | `unit` |
| --- | --- | --- | --- | --- | --- |
| `sensor-1` | cada segundo | entero aleatorio 0–100 | `random-value` | `random-simulation` | `null` |
| `sensor-2` | en cada pulsación del botón | `2` | `button` | `button-press` | `null` |
| `sensor-3` | al cambiar la distancia | número con 1 decimal, o `null` sin eco | `distance` | `ultrasonic-hcsr04` | `cm` |
| `sensor-4` | al girar o pulsar el encoder | `{"position":int,"pressed":bool}` | `rotary-encoder` | `encoder-ky040` | `null` |

`feature_of_interest` es `esp32-device` en todos. Todos envían su primera
lectura al arrancar.

- **Botón:** una sola observación al pulsar (flanco de bajada, antirrebote de
  50 ms sin `delay()`); mantenerlo pulsado no repite.
- **HC-SR04:** mide cada 100 ms. Envía cuando la distancia cambia 2 cm o más
  (`US_THRESHOLD_CM`) desde el último valor enviado, o cuando pasa de número a
  `null` o al revés; como mucho 5 observaciones por segundo. Rango útil
  2–400 cm; fuera de él, o sin eco en 25 ms, el valor es `null`.
- **KY-040:** la cuadratura de CLK/DT se decodifica por interrupciones con una
  tabla de estados. El módulo da 4 transiciones por muesca (detent) y solo se
  cuenta un paso al completarlas, así que `position` sube o baja 1 por muesca.
  Si gira al revés de lo esperado, intercambia CLK y DT. Envía al cambiar la
  posición o el pulsador SW (antirrebote de 50 ms), como mucho 10
  observaciones por segundo; tras una ráfaga manda solo la última posición.

## Cableado del botón

Pulsador entre el GPIO `BUTTON_PIN` (por defecto **GPIO 4**) y **GND**. El
pin usa `INPUT_PULLUP`, así que no hace falta resistencia. Para probar sin
cablear, pon `#define BUTTON_PIN 0` en `secrets.h` y usa el botón **BOOT**
de la placa (GPIO 0; no lo mantengas pulsado al arrancar o entrará en modo
de flasheo).

## Placas

| Entorno | Módulo |
| --- | --- |
| `esp32dev` (por defecto) | ESP32-WROOM-32 / 32E |
| `esp32-s3-devkitc-1` | ESP32-S3-WROOM |

Si no sabes cuál tienes, mira la serigrafía del módulo metálico.

## Cableado del HC-SR04 (sensor-3)

> **⚠ El pin Echo saca 5 V: no lo conectes directo al ESP32.** El HC-SR04
> necesita 5 V, así que **VCC va a 5V/VIN**, y entonces Echo devuelve pulsos
> de 5 V. Los GPIO del ESP32 aguantan como mucho 3,3 V: pon un **divisor de
> tensión** en Echo.

```text
Echo ──[ 1 kΩ ]──┬── GPIO Echo
                 │
              [ 2 kΩ ]
                 │
                GND
```

El divisor de 1 kΩ y 2 kΩ deja unos 3,3 V en el GPIO; 10 kΩ y 20 kΩ también
valen. Otra opción es el **HC-SR04P**, que funciona a 3,3 V: se alimenta de
3V3 y no necesita divisor. Trig se puede atacar directamente desde el GPIO de
3,3 V.

| HC-SR04 | ESP32 (WROOM-32) | ESP32-S3 |
| --- | --- | --- |
| VCC | **5V/VIN** | **5V/VIN** |
| Trig | GPIO 26 | GPIO 6 |
| Echo | GPIO 27 **por el divisor** | GPIO 7 **por el divisor** |
| GND | GND (común) | GND (común) |

## Cableado del KY-040 (sensor-4)

> **⚠ Alimenta el encoder a 3V3, nunca a 5V.** El módulo trae resistencias
> de pull-up hacia «+»; alimentado a 5 V pondría 5 V en los GPIO.

| KY-040 | ESP32 (WROOM-32) | ESP32-S3 |
| --- | --- | --- |
| + | **3V3** | **3V3** |
| GND | GND | GND |
| CLK | GPIO 25 | GPIO 15 |
| DT | GPIO 33 | GPIO 16 |
| SW | GPIO 32 | GPIO 17 |

Los pines se cambian en `secrets.h` con `US_TRIG_PIN`, `US_ECHO_PIN`,
`ENC_CLK_PIN`, `ENC_DT_PIN` y `ENC_SW_PIN`. Al arrancar, el monitor serie
muestra todos los pines en uso.

## 1. Credenciales

```bash
cp apps/reader/examples/esp32/src/secrets.example.h apps/reader/examples/esp32/src/secrets.h
```

Rellena `WIFI_SSID`, `WIFI_PASSWORD` y, si quieres, `READER_TOKEN`,
`MANAGER_URLS` (separadas por comas), `MANAGER_TOKEN`, `BUTTON_PIN`, los
pines de los sensores y `US_THRESHOLD_CM`. `secrets.h` está en
`.gitignore`; sin él la compilación se para con un `#error` que lo explica.

## 2. Compilar, flashear y monitorizar

```bash
pio run -d apps/reader/examples/esp32 -e esp32dev -t upload
pio device monitor -d apps/reader/examples/esp32 -e esp32dev
```

El monitor (115200 baudios) muestra la IP y `http://phonendo-reader.local/`.

## 3. Probar con curl

Sin token (`READER_TOKEN ""`):

```bash
R=http://phonendo-reader.local   # o http://<IP del monitor>
curl $R/health
curl $R/metadata
curl $R/devices
curl $R/devices/esp32-device
curl $R/devices/no-existe          # 404 {"error":"device_not_found",...}
curl -N $R/stream                  # ": connected" y los eventos en vivo
```

Respuestas esperadas (el JSON sale compacto, en una línea):

```text
$ curl $R/devices
[{"deviceId":"esp32-device","deviceType":"ESP32","sensors":["sensor-1","sensor-2","sensor-3","sensor-4"]}]

$ curl $R/devices/esp32-device
{"schemaVersion":"phonendo.device.v1","readerId":"reader-esp32-01","deviceId":"esp32-device","deviceType":"ESP32","creationDatetime":null,"sensors":["sensor-1","sensor-2","sensor-3","sensor-4"]}

$ curl -N $R/stream
: connected

event: observation
data: {"eventType":"observation","readerId":"reader-esp32-01","deviceId":"esp32-device","payloadFormat":"application/json","payload":{"observation_id":"…","observable_property":"random-value","simple_result":57,"phenomenon_time":"2026-10-25T13:00:01.000123+00:00","feature_of_interest":"esp32-device","procedure":"random-simulation","device_id":"esp32-device","sensor_id":"sensor-1","unit":null}}

event: observation
data: {"eventType":"observation","readerId":"reader-esp32-01","deviceId":"esp32-device","payloadFormat":"application/json","payload":{"observation_id":"…","observable_property":"button","simple_result":2,"phenomenon_time":"2026-10-25T13:00:01.402311+00:00","feature_of_interest":"esp32-device","procedure":"button-press","device_id":"esp32-device","sensor_id":"sensor-2","unit":null}}

event: observation
data: {"eventType":"observation","readerId":"reader-esp32-01","deviceId":"esp32-device","payloadFormat":"application/json","payload":{"observation_id":"…","observable_property":"distance","simple_result":42.7,"phenomenon_time":"2026-10-25T13:00:01.512006+00:00","feature_of_interest":"esp32-device","procedure":"ultrasonic-hcsr04","device_id":"esp32-device","sensor_id":"sensor-3","unit":"cm"}}

event: observation
data: {"eventType":"observation","readerId":"reader-esp32-01","deviceId":"esp32-device","payloadFormat":"application/json","payload":{"observation_id":"…","observable_property":"distance","simple_result":null,"phenomenon_time":"2026-10-25T13:00:01.713420+00:00","feature_of_interest":"esp32-device","procedure":"ultrasonic-hcsr04","device_id":"esp32-device","sensor_id":"sensor-3","unit":"cm"}}

event: observation
data: {"eventType":"observation","readerId":"reader-esp32-01","deviceId":"esp32-device","payloadFormat":"application/json","payload":{"observation_id":"…","observable_property":"rotary-encoder","simple_result":{"position":-3,"pressed":false},"phenomenon_time":"2026-10-25T13:00:01.733050+00:00","feature_of_interest":"esp32-device","procedure":"encoder-ky040","device_id":"esp32-device","sensor_id":"sensor-4","unit":null}}
```

Con `sensor-1` emitiendo cada segundo, el `: heartbeat` de 15 s solo aparece
si el stream se queda sin eventos.

Con token:

```bash
T=mi-token
curl -H "Authorization: Bearer $T" $R/metadata
curl -N -H "Authorization: Bearer $T" $R/stream
curl -i $R/metadata                # 401 sin cabecera
```

## Comportamiento y límites

- Hora: NTP (`pool.ntp.org`) en UTC. Hasta que sincroniza, `phenomenon_time`
  sale en `1970-01-01T…+00:00` y el monitor lo avisa; los Managers pueden
  rechazar esas lecturas.
- `/stream`: como mucho 4 suscriptores (`PHONENDO_MAX_SSE_CLIENTS`; el
  siguiente recibe 503) y 16 eventos en cola por suscriptor; quien se quede
  atrás recibe `event: stream_closed` y se desconecta. Sin eventos se manda
  `: heartbeat` cada 15 s.
- La medida del HC-SR04 bloquea el bucle hasta 25 ms (`pulseIn`) cada
  100 ms cuando no hay eco.
- El servidor es síncrono: un Manager que no responde bloquea el bucle hasta
  su timeout (5 s) y retrasa el stream. Un Manager caído no impide entregar a
  los demás.
- `creationDatetime` de `/devices/{id}` es `null`.
- Usa la tabla de particiones `huge_app.csv` (app de 3 MB, sin OTA): con
  WiFi, HTTPClient, WebServer y mDNS la imagen no cabe en la de 1,3 MB.
