# Manager

Coordina la recepción, verificación y almacenamiento de las observaciones.
Consulta el dispositivo en Storage, calcula el hash del contenido Captured y lo
manda al Verifier. Solo guarda el evento Verified tras una verificación positiva.
Publisher está pendiente de integración.

## Organización

- `manager.py`: configuración y arranque.
- `core.py`: procesamiento, prioridad HTTP y cola de reintentos.
- `server.py`: endpoints HTTP y streams de salida.
- `client.py`: comunicaciones con otros servicios y consumo del Reader.
- `config.py`: configuración del servicio.
- `manager_support/event_auth.py`: cálculo del hash con la clave compartida.

El hash cubre el sobre Captured completo, salvo el propio `managerHash`. Manager
y Verifier deben compartir `MANAGER_PASSWORD`. La firma RSA del resultado la
produce el Verifier.

## Entrada y resultado

| Ruta | Uso |
| --- | --- |
| `GET /` | Comprobar que el servicio responde. |
| `POST /registerDevice` | Registrar un dispositivo en Storage. |
| `POST /newEvent` | Recibir y procesar una observación. |

Los POST requieren `token` en el JSON, igual a `API_TOKEN_MANAGER`.
`/newEvent` requiere `readerId`, `deviceId`, `eventType`, `payloadFormat` y `payload`.

| Resultado de `/newEvent` | HTTP |
| --- | --- |
| Verificado y guardado | `200 Verified` |
| Timeout; pendiente en memoria | `202 Pending` |
| Rechazo explícito del Verifier | `422 Rejected` |
| Dispositivo no registrado | `404 Failed` |
| Fallo de servicio interno | `502 Failed` |

Un token inválido devuelve 401; campos ausentes, 400. Un fallo al calcular el hash
devuelve 500. Las respuestas de procesamiento incluyen `eventId`; los fallos y
pendientes también indican `stage`.

## Streams

`MANAGER_CONFIG_PATH` apunta al JSON de configuración; por defecto se usa
`config.json` junto al servicio. `stream.enabled` habilita las funciones SSE:

| Opción | Comportamiento |
| --- | --- |
| `stream.readers` | Consume `/metadata` y `/stream` de las URLs base en `services.readers`. |
| `stream.verifiers` | Expone `/stream/verifier` con eventos Captured. |
| `stream.storages` | Expone `/stream/storage` con eventos Verified. |

El Reader puede requerir `API_TOKEN_READER` como Bearer. Los streams de salida
requieren Bearer con `API_TOKEN_VERIFIER` o `API_TOKEN_STORAGE`, respectivamente.
El Verifier ya puede consumir el stream del Manager; Storage todavía no lo consume.
El Manager aún no consume los resultados SSE del Verifier para continuar el guardado:
el flujo completo actual usa HTTP para verificar y guardar.

Desde que llega un `/newEvent` válido de un `readerId`, se ignora su entrada SSE
hasta reiniciar el Manager. Los dispositivos deben estar registrados previamente.
Los streams son en vivo, sin historial ni confirmación de entrega.

## Configuración y reintentos

Las conexiones se definen en las listas JSON `services.verifiers`,
`services.storages` y `services.readers`; cada entrada es una URL base o un objeto
`{"url": "http://servicio:puerto", "token": "..."}`. Los tokens del entorno
se usan como valor por defecto cuando la entrada no define uno.

Cada evento se envía a todos los Verifiers HTTP, con trabajo y clave propios para
cada relación. Un rechazo afecta a esa relación; un timeout encola solo ese trabajo.
Los envíos se lanzan en paralelo. Con varios Verifiers, `/newEvent` devuelve `207`
con `results`: URL del Verifier, resultado y `httpStatus` por relación.
Los eventos aceptados se envían a los Storages configurados; al reintentar una
escritura se omiten los destinos ya confirmados.

La publicación SSE es independiente: publica una observación sin esperar a ningún
Verifier. Con lista HTTP vacía y stream de Verifier habilitado responde `200 Streamed`;
esto indica publicación al stream, no verificación ni guardado. Sin ningún destino
HTTP ni stream de Verifier devuelve `503`.

| Variable | Valor por defecto | Uso |
| --- | --- | --- |
| `MANAGER_HTTP_TIMEOUT_SECONDS` | `10` | Timeout HTTP. |
| `MANAGER_QUEUE_SIZE` | `1000` | Capacidad de la cola de pendientes. |
| `MANAGER_RETRY_INTERVAL_SECONDS` | `5` | Intervalo entre reintentos. |

Un rechazo explícito descarta el evento. Un timeout lo encola y el reintento
continúa desde la etapa pendiente. Al llenarse la cola, se descarta el pendiente
más antiguo. La cola se pierde al reiniciar. Los reintentos conservan la clave del
evento; repetir un POST como petición nueva genera otra clave.

## Pruebas

Desde la raíz, con el entorno descrito en el [README principal](../../README.md):

```sh
./tools/test.sh 'test_manager_*.py'
./tools/test_integration.sh
```

La integración arranca los cuatro servicios con puertos y almacenamiento temporales,
comprueba SSE, firmas y conservación del dato, y cierra los procesos al terminar.

[Diagramas generales](../../docs/diagramas.md).

Las utilidades de este servicio están en `manager_support/`. No requieren código de otros servicios.
