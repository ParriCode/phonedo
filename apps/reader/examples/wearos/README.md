# Reader Phonendo en Wear OS

Ejemplo de plataforma para el **OnePlus Watch 3** (Wear OS 5 / Android 14,
API 34, arm64). Mide el pulso con Health Services y sirve el mismo contrato
que el Reader Python y el ejemplo ESP32: `/health`, `/metadata`, `/devices`,
`/devices/{id}` y `/stream` (SSE), y envía cada evento a uno o varios
Managers (`POST <url>/newEvent` con `token` en el cuerpo).

## Reparto

| Capa | Qué hace | Dónde |
| --- | --- | --- |
| C++ (NDK) | `ReaderCore` con un dispositivo y un sensor, `ReaderService` con `StreamOutput`, JSON de los endpoints, sobre del evento, colas SSE | `app/src/main/cpp/wear_reader.*` + `apps/reader/cpp` |
| JNI | traduce tipos y serializa todas las llamadas con un mutex (la librería no es segura entre hilos) | `app/src/main/cpp/reader_jni.cpp` |
| Kotlin | Health Services, servicio en primer plano, servidor HTTP/1.1, envío a los Managers, pantalla | `app/src/main/java/...` |

`CMakeLists.txt` compila los fuentes de `apps/reader/cpp/core` y
`apps/reader/cpp/server` directamente; no hay copias.

## Datos

Un dispositivo `oneplus-watch-3` (tipo `smartwatch`, plataforma `wearos`) con
un sensor:

| Sensor | Cuándo emite | `simple_result` | `observable_property` | `procedure` | `unit` |
| --- | --- | --- | --- | --- | --- |
| `heart-rate` | cada muestra de `HEART_RATE_BPM` (≈ 1 s) | número (bpm) | `heart-rate` | `health-services-ppg` | `bpm` |

`feature_of_interest` es `oneplus-watch-3`, como en el ESP32 es el propio
dispositivo. `phenomenon_time` es la hora de la muestra (no la de llegada), en
UTC. Las muestras a 0 (Health Services aún no ha captado el pulso) se
descartan.

## 1. Entorno: devenv

Todo sale de Nix: JDK 17, Gradle 8, SDK (plataformas 34–36, build-tools,
platform-tools), NDK 27.0.12077973, CMake 3.22.1 y la imagen Wear OS API 34
x86_64. **No instales nada a mano** (ni Android Studio ni `sdkmanager`): si
Gradle se queja de

```text
Failed to install the following SDK components: <nombre>
The SDK directory is not writable (/nix/store/...)
```

añade ese componente al bloque `android` de `devenv.nix`.

```bash
cd apps/reader/examples/wearos
devenv shell          # o direnv allow, si usas direnv
```

La primera vez descarga varios GB (SDK, NDK, imagen del emulador).

## 2. Credenciales

```bash
cp secrets.example.properties secrets.properties
```

Rellena `READER_ID`, `READER_PORT` (8080 por defecto), `READER_TOKEN`,
`MANAGER_URLS` (separadas por comas) y `MANAGER_TOKEN`. `secrets.properties`
está en `.gitignore`; sin él Gradle se para con un mensaje que lo explica. Los
valores entran en `BuildConfig`: tras cambiarlos hay que recompilar.

## 3. Comandos (dentro de `devenv shell`)

| Comando | Qué hace |
| --- | --- |
| `build` | `gradle assembleDebug` → `app/build/outputs/apk/debug/app-debug.apk` |
| `unit` | pruebas JVM de la parte Kotlin (rutas, Bearer, SSE, cuerpo de `/newEvent`) |
| `native-test` | compila el puente C++ con g++ en el host y comprueba el sobre |
| `instalar` | instala el APK en lo que vea adb |
| `logs` | logcat de la app |
| `pair` | instrucciones y `adb pair` para la depuración por Wi‑Fi |
| `avd` / `emu` | crea (una vez) y arranca el emulador Wear OS redondo |

Si hay varios dispositivos a la vez (reloj y emulador), elige uno:
`instalar -s <serie>` y `logs -s <serie>`, o exporta `ANDROID_SERIAL=<serie>`.
`adb devices` da las series (`emulator-5554`, `192.168.1.50:41234`...).

## 4. Instalar en el reloj

El OnePlus Watch 3 no tiene USB de datos: se depura por Wi‑Fi.

1. En el reloj: **Ajustes → Sistema → Información** y toca **Número de
   compilación** siete veces para activar las opciones de desarrollador.
2. **Ajustes → Opciones de desarrollador**: activa **Depuración ADB** y
   **Depuración inalámbrica**. El reloj y el ordenador deben estar en la misma
   red Wi‑Fi.
3. **Depuración inalámbrica → Emparejar dispositivo nuevo** muestra una IP,
   un puerto de emparejado y un código:

   ```bash
   pair 192.168.1.50:37123 123456
   adb connect 192.168.1.50:41234     # el puerto de la pantalla principal
   adb devices
   build && instalar -s 192.168.1.50:41234
   ```

4. Abre **Phonendo Reader**, pulsa **Empezar** y acepta los permisos de
   sensores corporales y notificaciones. La pantalla muestra el pulso, la
   `IP:puerto` del servidor, los suscriptores SSE y el último POST.

En el emulador (`emu`) no hay sensor real: Health Services solo da pulso con
sus datos sintéticos, que se activan desde las herramientas de Health Services
del emulador (el procedimiento cambia según la versión de la imagen; ver la
guía «Synthetic data» de Health Services en developer.android.com). Esto no
se ha probado aún con esta app.

## 5. Probar con curl

```bash
R=http://<IP que muestra el reloj>:8080
curl $R/health
curl $R/metadata
curl $R/devices
curl $R/devices/oneplus-watch-3
curl $R/devices/no-existe          # 404 {"error":"device_not_found",...}
curl -N $R/stream                  # ": connected" y los eventos en vivo
```

```text
$ curl $R/devices
[{"deviceId":"oneplus-watch-3","deviceType":"smartwatch","sensors":["heart-rate"]}]

$ curl -N $R/stream
: connected

event: observation
data: {"eventType":"observation","readerId":"reader-wearos-01","deviceId":"oneplus-watch-3","payloadFormat":"application/json","payload":{"observation_id":"…","observable_property":"heart-rate","simple_result":72,"phenomenon_time":"2026-10-25T13:00:01.250000+00:00","feature_of_interest":"oneplus-watch-3","procedure":"health-services-ppg","device_id":"oneplus-watch-3","sensor_id":"heart-rate","unit":"bpm"}}
```

Con token: `curl -H "Authorization: Bearer $T" $R/metadata`; sin la cabecera,
`401 {"error":"unauthorized"}`.

En el emulador el servidor no es accesible desde fuera sin redirigir el
puerto: `adb -s emulator-5554 forward tcp:8080 tcp:8080` y `R=http://127.0.0.1:8080`.

## Comportamiento y límites

- **Red:** el reloj solo es accesible con el Wi‑Fi activo y en la misma red
  que quien lo consulta. Wear OS apaga el Wi‑Fi cuando hay Bluetooth con el
  móvil; el servicio lo pide (`requestNetwork` con `TRANSPORT_WIFI`) mientras
  mide. El POST a los Managers usa la red por defecto, así que también sale por
  el proxy Bluetooth del móvil.
- `/stream`: como mucho 4 suscriptores (el siguiente recibe 503) y 64 eventos
  en cola por suscriptor; quien se quede atrás recibe `event: stream_closed`.
  Sin eventos se manda `: heartbeat` cada 15 s. Al pulsar **Parar** cada
  cliente recibe `stream_closed` antes de cerrarse el socket.
- **Managers:** cada uno tiene su hilo y su cola (32 eventos, se descarta el
  más antiguo); uno caído no retrasa a los demás ni a la medida. Timeout de
  5 s. Las URLs `http://` funcionan porque la app permite tráfico en claro.
- Mientras mide hay un wake lock parcial: la batería baja más rápido.
- `creationDatetime` de `/devices/{id}` es `null`.
- Wear OS 6 (Android 16) sustituye `BODY_SENSORS` por permisos de Health
  Connect; con `targetSdk 34` el permiso antiguo sigue funcionando.
