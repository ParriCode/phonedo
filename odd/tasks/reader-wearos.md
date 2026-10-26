# Reader Wear OS: pulso del OnePlus Watch 3

## Objetivo
Una app Wear OS para el OnePlus Watch 3 que lee el pulso (bpm) y lo publica
con la librería C++ del Reader (`apps/reader/cpp`), con el mismo contrato que
el Reader Python y el ejemplo ESP32. Todo el entorno se levanta con devenv.

## Por qué
Es el caso de uso A de `AGENTS.md` (adherencia a rehabilitación cardiaca): el
pulso real de un reloj alimenta el flujo Reader → Manager → Verifier → Storage.

## Decisiones
- **Transporte: los dos, como el ESP32** (decisión del usuario, 2026-10-25).
  - POST a `<manager>/newEvent` (token en el cuerpo, como `manager_output.py`).
    Funciona por Wi‑Fi o por el proxy Bluetooth del móvil.
  - Servidor en el reloj: `/health`, `/metadata`, `/devices`,
    `/devices/{id}`, `/stream` (SSE). Solo alcanzable con el Wi‑Fi del reloj
    activo y en la misma red que el Manager.
- El OnePlus Watch 3 (43 y 46 mm) tiene Wi‑Fi 2,4/5 GHz y BT 5.2; no tiene
  red móvil (eso es el Watch 3 Pro).
- **Reparto C++/Kotlin:** C++ (NDK + JNI) hace todo lo del Reader: core,
  `ReaderService`, `ObservationStream`, JSON del sobre y de los endpoints.
  Kotlin hace lo de Android: Health Services (`HEART_RATE_BPM`), servicio en
  primer plano, sockets del servidor y cliente HTTP hacia los Managers.
- La librería C++ no es segura entre hilos: el puente JNI serializa todas las
  llamadas con un mutex.

## Restricciones
- Python del Reader es solo lectura (`apps/reader/python`, `examples/linux`).
- `AGENTS.md`: sin commits salvo que el humano lo pida, sin atribución a IA;
  comentarios y README en castellano.
- Nada instalado fuera de Nix: SDK, NDK, CMake, imagen Wear OS y Gradle los
  declara `devenv.nix`. Si Gradle pide un componente, se declara ahí.
- Credenciales (URL del Manager, token) fuera de git.

## Alcance autorizado
`apps/reader/examples/wearos/**` (nuevo), sección Wear OS de
`apps/reader/README.md`, este documento. `apps/reader/cpp/**` solo si un
fallo real de compilación con el NDK lo exige.

## Tareas
- [x] T1 devenv: `devenv.nix`, `devenv.yaml`, `.envrc`, `.gitignore`; JDK 17,
  Gradle, SDK + NDK + CMake, imagen de sistema Wear OS x86_64 y scripts
  (`build`, `instalar`, `avd`, `emu`, `logs`). Ruta: delegada (writer).
- [x] T2 Puente nativo: `CMakeLists.txt` que compila `cpp/core` y `cpp/server`
  y `reader_jni.cpp`. Ruta: delegada (writer).
- [x] T3 App Kotlin: Health Services, servicio en primer plano, servidor
  HTTP/SSE, envío a Managers, pantalla mínima. Ruta: delegada (writer).
- [x] T4 README del ejemplo y sección en `apps/reader/README.md`. Ruta:
  delegada (writer).

## Comprobaciones
- `devenv shell` evalúa y `build` genera el APK debug.
- Tests JVM de la parte pura (rutas HTTP, tramas SSE, cuerpo de `/newEvent`).
- Host: el puente C++ sin JNI compila con g++ y produce el sobre esperado.
- Manual (usuario): instalar en el reloj, ver el bpm y `curl` a `/stream`.

## Progreso
- 2026-10-25: exploración hecha, transporte decidido. Espejo Engram
  pendiente: herramientas de Engram no disponibles en esta sesión.
- 2026-10-25: T1–T4 hechas (writer delegado). Elección: Wear OS API 34
  (`android-wear`, x86_64), igual que el reloj (Wear OS 5 = Android 14).
  AGP 8.13.1, Kotlin 2.2.21, Gradle 8.14 (`gradle_8` de nixpkgs, sin
  wrapper), NDK 27.0.12077973, CMake 3.22.1, compileSdk 36, targetSdk 34.
  `devenv.lock` copiado de comiditas (mismo nixpkgs). `apps/reader/cpp` sin
  cambios.
  Evidencia:
  - `devenv shell -- true`: exit 0 (descarga de las imágenes Wear OS 34 y 35).
  - `devenv shell -- build`: BUILD SUCCESSFUL; `app-debug.apk` con
    `libphonendo_reader.so` para arm64-v8a y x86_64 (13 símbolos JNI).
  - `devenv shell -- unit`: 21 pruebas JVM en verde (HttpProtocol 10,
    SseSession 6, ManagerPoster 5). Las pruebas se escribieron antes del
    código, pero el RED no se ejecutó (devenv aún descargaba); en su lugar,
    una mutación (`>=` → `>` en el latido) hizo fallar
    `heartbeatOnlyAfterFifteenIdleSeconds` y se revirtió.
  - `devenv shell -- native-test`: «OK: puente nativo» (g++ en el host, sin
    JNI: sobre con eventType, deviceId, unit bpm, simple_result numérico y
    hora ISO UTC).
  - Primer `unit` falló: faltaba Guava (`ListenableFuture`); añadida.
  - Reloj real: ABI `armeabi-v7a` (Wear OS de 32 bits); añadida a
    `abiFilters` y APK instalado (`Success`). Script `install` renombrado a
    `instalar` (chocaba con el `install` de coreutils).
  - Pendiente: probar el bpm y `/stream` en el reloj; emulador sin probar.
  - Espejo Engram: sigue pendiente.

## Siguiente paso
Prueba manual en el reloj (usuario): `pair`, `adb connect`, `install -s`,
conceder permisos, ver el bpm y `curl -N` a `/stream`. Engram: resincronizar
el espejo cuando esté disponible.
