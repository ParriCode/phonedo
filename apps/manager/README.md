# Manager: resultado del procesamiento y autenticación

`server.py` mantiene las comprobaciones explícitas de campos de cada endpoint.

`POST /newEvent` responde 200 con `{eventId, status: "Verified"}` únicamente tras
verificación positiva y confirmación del guardado final. Errores: 422 para rechazo
del Verifier, 502 para fallos/respuestas incompatibles de servicios internos,
202 `{eventId, status: "Pending", stage}` para timeout y 500 para fallo de
configuración de la autenticación del evento.
El cuerpo de un error de procesamiento incluye `eventId` y `stage`.
Un timeout puede tener resultado incierto: el servicio remoto podría haber escrito.

`managerHash` contiene HMAC-SHA256 del sobre completo Captured (incluye UUID,
identidades, payload y fecha), excluyendo únicamente el propio `managerHash`.
Serialización compartida: JSON UTF-8 con claves ordenadas, separadores compactos,
sin escape ASCII y sin NaN/Infinity. Implementación: `sign_event()` en `apps/manager/utils.py` y
`verify_event()` en `apps/verifier/verifier.py`.
El Verifier comprueba el HMAC antes de producir su mensaje Verified firmado con RSA.
El HMAC conservado en Verified corresponde al sobre Captured original, no al sobre
modificado con estado Verified y campos del Verifier.

Manager y Verifier necesitan el mismo `MANAGER_PASSWORD` secreto en sus respectivos
`config.env` o entorno. El generador ya escribe la variable para ambos y exige que
esté definida, sin contraseña por defecto. Para una instalación existente hay que
configurar también el Verifier. No ejecutar el generador sobre configuraciones
personalizadas sin revisar los valores de entrada, pues reescribe los archivos.
No se guarda la clave ni su derivación como managerHash del registro de dispositivo.
Los hashes antiguos de eventos no son HMAC válidos y no se aceptan como tales.

Esto es autenticación simétrica: ambas partes conocen el secreto y pueden producir
un HMAC. No es una firma del Manager verificable mediante una clave pública.

El Manager conserva `Captured` en memoria durante la petición y **solo escribe en
Storage el mensaje `Verified`**. Si el Verifier rechaza explícitamente (HTTP 400/422
o `verified=false`), el evento se descarta sin escritura ni reintento. Un timeout de
consulta, verificación o escritura deja el trabajo en una cola volátil y devuelve
`202 Pending` con el `eventId`; el reintento continúa en la etapa donde se produjo.
Esto no equivale a una aceptación verificada.

| Opción | Default | Uso |
| --- | --- | --- |
| `MANAGER_HTTP_TIMEOUT_SECONDS` | `10` | Timeout de las llamadas HTTP a Storage y Verifier. |
| `MANAGER_QUEUE_SIZE` | `1000` | Número máximo de eventos pendientes en memoria. |
| `MANAGER_RETRY_INTERVAL_SECONDS` | `5` | Segundos entre intentos del trabajador de cola. |

Los tres valores deben ser positivos. Al llenarse la cola se descarta el pendiente
más antiguo para admitir el nuevo y se registra su `eventId` en logs. Hay un único
trabajador de reintento; el evento que está procesando no ocupa una plaza de espera.
La cola se pierde al reiniciar el proceso, no proporciona durabilidad ni consulta
HTTP de estado. El `eventId` se conserva en sus reintentos internos para evitar
una segunda clave en Storage, pero una petición nueva del Reader aún recibe otra
UUID: no hay idempotencia entre peticiones independientes. Un timeout de escritura
puede haber llegado a Storage; el reintento usa la misma clave y valor.

La llamada al Publisher permanece desactivada.

Pruebas (entorno con dependencias de Manager y Verifier instaladas):

```sh
python -m unittest discover -s tests/app_tests -p test_manager_processing.py -v
```

## Streams SSE para servicios

`ManagerServer` (Flask) se configura mediante `ManagerConfig`, que carga el JSON
indicado por `MANAGER_CONFIG_PATH` (por defecto `apps/manager/config.json`).
Los endpoints se registran solo cuando `stream.enabled=true` y la opción del
servicio correspondiente también está habilitada:

| Ruta | Opción JSON | Autenticación | Evento |
| --- | --- | --- | --- |
| `GET /stream/verifier` | `stream.verifiers` | `Authorization: Bearer <API_TOKEN_VERIFIER>` | Sobre `Captured` preparado para verificar. |
| `GET /stream/storage` | `stream.storages` | `Authorization: Bearer <API_TOKEN_STORAGE>` | Sobre `Verified` devuelto por el Verifier. |

El Manager emite `observation` con `id` igual al identificador del evento. Al
conectar, manda `: connected`; durante la inactividad, `: heartbeat` cada 15 s.
Cada suscriptor tiene una cola de 256 elementos; al llenarse se desconecta ese
suscriptor y los demás continúan. No hay historial, replay ni confirmación de
consumo, por lo que estos streams no sirven todavía para garantizar entrega.

**Integración pendiente:** Storage y Verifier no consumen estos SSE. El flujo
operativo actual sigue usando `POST /verify` y `POST /events`; habilitar los
streams no sustituye esas llamadas. El evento puede aparecer otra vez en el
stream si el Manager reintenta tras timeout, con el mismo `id`.

Configuración de ejemplo:

```json
{
  "stream": {
    "enabled": true,
    "verifiers": true,
    "storages": true
  }
}
```

`stream.readers` activa el consumo de los streams del Reader.
`stream.publishers` permanece reservado para trabajo futuro.

## Consumo del stream del Reader

Con `stream.enabled=true`, `stream.readers=true` y URLs base en
`services.readers`, `ManagerClient` consulta `/metadata` de cada Reader y se
suscribe a su `/stream` SSE. Procesa los eventos `observation` mediante el mismo
flujo de `/newEvent`; si se corta la conexión, vuelve a intentarlo cada 5 s.
Una URL de ejemplo es `http://127.0.0.1:3002` (sin `/stream`). Si el Reader
requiere autenticación, `API_TOKEN_READER` se envía como Bearer en ambas rutas.

El `readerId` de cada observación debe coincidir con el anunciado en `/metadata`.
En cuanto un Reader envía un `/newEvent` válido, el Manager usa HTTP como origen
preferente para ese `readerId` durante el resto de la vida del proceso y descarta
sus observaciones SSE. Otros Readers siguen consumiéndose por stream. Esta
preferencia vive en memoria y se restablece al reiniciar el Manager.

El stream del Reader es en vivo: no ofrece replay. Los dispositivos deben estar
registrados en Storage antes de procesar sus observaciones, igual que por HTTP.

## Organización

- `manager.py`: configuración y composición del servicio.
- `core.py`: procesamiento, firma, prioridad HTTP y cola de reintentos.
- `server.py`: endpoints HTTP y streams de salida.
- `client.py`: llamadas a servicios y consumo del stream del Reader.
- `utils.py`: firma del contenido.

Para comprobar el proyecto: `tools/build.sh` y `tools/test.sh`.
Prepara el entorno con `python3 -m venv .venv` y
`.venv/bin/python -m pip install -r tests/requirements.txt`.
El script de pruebas admite un patrón: `tools/test.sh 'test_manager_*.py'`.
