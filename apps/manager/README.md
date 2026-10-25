# Manager

`managerId` en `config.json` (o `MANAGER_ID`) identifica esta instancia; usa un
valor distinto por Manager. Sin configurarlo se genera uno por arranque.
`POST /signBatch` exige `managerId`, `readerId` y `verifierId` además del lote.
Selecciona el Verifier consultando `/metadata` en las URLs configuradas en
`services.verifiers` o `subscriptions.verifiers`; nunca firma con otro por defecto.

Coordina la recepción, verificación y almacenamiento de las observaciones.
Calcula el hash del contenido Captured y lo
manda al Verifier. Solo guarda el evento Verified tras una verificación positiva.
Publisher está pendiente de integración.

## Organización

- `manager.py`: configuración y arranque.
- `core.py`: procesamiento, selección de transporte por Reader y cola de reintentos.
- `server.py`: endpoints HTTP y streams de salida.
- `client.py`: comunicaciones con otros servicios y consumo del Reader.
- `config.py`: configuración del servicio.
- `manager_support/event_auth.py`: cálculo del hash con la clave compartida.

El hash cubre el sobre Captured completo, salvo el propio `managerHash`. Manager
y Verifier deben compartir `MANAGER_PASSWORD`. La firma ed25519 del resultado la
produce el Verifier.

## Entrada y resultado

| Ruta | Uso |
| --- | --- |
| `GET /` | Comprobar que el servicio responde. |
| `POST /newEvent` | Recibir y procesar una observación. |
| `POST /signBatch` | Reenviar a los Verifiers de `services.verifiers` la firma de un lote; devuelve la primera respuesta válida. |

Los POST requieren `token` en el JSON, igual a `API_TOKEN_MANAGER`.
`/newEvent` requiere `readerId`, `deviceId`, `eventType`, `payloadFormat` y `payload`.

| Resultado de `/newEvent` | HTTP |
| --- | --- |
| Verificado y guardado | `200 Verified` |
| Timeout; pendiente en memoria | `202 Pending` |
| Rechazo explícito del Verifier | `422 Rejected` |
| Fallo de servicio interno | `502 Failed` |
| Reader con SSE ya seleccionado | `409 Conflict` |

Un token inválido devuelve 401; campos ausentes, 400. Un fallo al calcular el hash
devuelve 500. Las respuestas de procesamiento incluyen `eventId`; los fallos y
pendientes también indican `stage`.

## Stream propio, suscripciones y salidas

Las tres capacidades son independientes:

```json
{
  "stream": {"enabled": true},
  "subscriptions": {
    "readers": ["http://reader:3002"],
    "verifiers": ["http://verifier:5000"],
    "storages": ["http://storage:5000"]
  },
  "outputStreams": {"verifiers": true, "storages": true},
  "services": {"verifiers": [], "storages": ["http://storage:5000"]}
}
```

| Configuración | Comportamiento |
| --- | --- |
| `stream.enabled` | Expone `/stream` con eventos Captured y Verified tratados por el Manager. Bearer `API_TOKEN_MANAGER`. |
| `subscriptions.readers` | Consume `/metadata` y `/stream` de los Readers. |
| `subscriptions.verifiers` | Consume `/stream` de Verifiers. Correlaciona sus resultados con eventos emitidos por este Manager y continúa el guardado. |
| `subscriptions.storages` | Consume `/stream` de Storages como confirmaciones de escritura; no vuelve a guardar esos datos. |
| `outputStreams.verifiers` | Expone `/stream/verifier` con Captured. Bearer `API_TOKEN_VERIFIER`. |
| `outputStreams.storages` | Expone `/stream/storage` con Verified. Bearer `API_TOKEN_STORAGE`. |

Cada lista contiene URLs base u objetos `{"url": "...", "token": "..."}`.
`services.verifiers` y `services.storages` son destinos **HTTP**, distintos de
las suscripciones SSE. Para un recorrido de verificación solo por SSE, deja
`services.verifiers` vacío, activa `outputStreams.verifiers`, configura
`subscriptions.verifiers` y suscribe el Verifier a este Manager.

Las suscripciones no dependen de `stream.enabled` y las salidas específicas
funcionan aunque el `/stream` propio esté deshabilitado. El SSE publica sin
esperar a los suscriptores ni ofrece replay o confirmación de recepción.
El Manager conserva un máximo de `MANAGER_QUEUE_SIZE` correlaciones SSE en memoria;
al reiniciar se pierden. Ignora resultados ajenos, alterados respecto al Captured
o ya recibidos de la misma fuente. Al recibir un resultado guarda por HTTP; si esa llamada tiene timeout, entra en la cola habitual.

Cada Reader utiliza un único transporte con este Manager: el primer `/newEvent`
válido selecciona HTTP; un SSE establecido selecciona SSE. Con HTTP seleccionado,
el Manager no abre el stream de ese Reader. Con SSE seleccionado, `/newEvent`
devuelve 409. La selección dura hasta reiniciar el Manager, también durante una
desconexión SSE; el stream puede reconectarse, sin abrir conexiones simultáneas
para el mismo `readerId`. Un intento SSE fallido antes de establecerse libera la
reserva y permite HTTP. Cada observación contiene `readerId` y `deviceId`; no requiere
registro previo ni consultas de dispositivos. Storage decide cómo organizar su base de datos.

Para Verifier y Storage, los destinos de `services` seleccionan HTTP. El Manager
omite sus suscripciones SSE a esos mismos destinos y rechaza con 409 las
suscripciones entrantes redundantes a `/stream/verifier` y `/stream/storage`.
Otros destinos pueden usar SSE simultáneamente. También se eliminan URLs repetidas
de las listas y se rechaza una segunda conexión SSE activa del mismo servicio.

Los Verifiers y Storages que se suscriben deben configurar `server.publicUrl`
(o `VERIFIER_PUBLIC_URL` / `STORAGE_PUBLIC_URL`) con su URL base, igual a la usada
en la configuración del Manager. La envían en `X-Phonendo-Service-URL`, junto al
Bearer habitual. Sin identidad válida, las salidas específicas devuelven 400.
Se normalizan barras finales, mayúsculas del host y puertos HTTP(S) por defecto;
los alias DNS distintos deben configurarse con una misma URL canónica. `/stream`
general queda destinado a monitorización; los servicios usan las salidas específicas.

Los logs `transport_selected`, `redundant_transport_rejected`,
`redundant_subscription_ignored`, `duplicate_subscription_ignored` y
`duplicate_destination_ignored` explican la selección o exclusión por servicio.
No se deduplican observaciones ni se cambian sus IDs o hashes.

## Configuración y reintentos

Las conexiones se definen en las listas JSON `services.verifiers`,
`services.storages` (HTTP) y `subscriptions.readers` (SSE); cada entrada es una URL base o un objeto
`{"url": "http://servicio:puerto", "token": "..."}`. Los tokens del entorno
se usan como valor por defecto cuando la entrada no define uno.

Cada evento se envía a todos los Verifiers HTTP, con trabajo y clave propios para
cada relación. Un rechazo afecta a esa relación; un timeout encola solo ese trabajo.
Los envíos se lanzan en paralelo. Con varios Verifiers, `/newEvent` devuelve `207`
con `results`: URL del Verifier, resultado y `httpStatus` por relación.
Los eventos aceptados se envían a los Storages configurados; al reintentar una
escritura se omiten los destinos ya confirmados.

La publicación SSE es independiente: publica una observación sin esperar a ningún
Verifier. Con lista HTTP vacía y stream propio o salida de Verifier habilitados responde `200 Streamed`;
esto indica publicación al stream, no confirmación del guardado. Sin ningún destino
HTTP ni stream de salida devuelve `503`.

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

## Docker

Desde la raíz del proyecto:

```sh
docker build -t phonendo-manager apps/manager
```

[Arranque conjunto, configuración y pruebas](../../deploy/docker/README.md).

Si un evento ya verificado se entrega solo mediante streams, el resultado es
`200 Streamed`: no confirma que Storage lo haya recibido o escrito.
