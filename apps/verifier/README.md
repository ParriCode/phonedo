# Verifier

Si se configura `subscriptions.managers`, define `server.publicUrl` (o
`VERIFIER_PUBLIC_URL`) con la URL base del Verifier usada por los Managers,
por ejemplo `http://verifier:5000`. El suscriptor envía esta identidad en
`X-Phonendo-Service-URL`. El Manager rechaza con 409 la conexión SSE si ya
utiliza HTTP con este Verifier o existe otra suscripción activa de él.

Valida los eventos Captured recibidos del Manager: comprueba sus campos, formato,
fecha y hash del contenido. Si los acepta, produce un evento Verified con firma
ed25519. Un rechazo no se publica como resultado verificado.

## Endpoints

| Ruta | Uso |
| --- | --- |
| `GET /` | Comprobar que el servicio responde. |
| `POST /verify` | Verificar el evento enviado en `message`. |
| `POST /signBatch` | Firmar con ed25519 un lote de 32 eventos ya verificados. |
| `GET /stream` | Recibir eventos Verified por SSE. |

El POST requiere `token` en el JSON, igual a `API_TOKEN_VERIFIER`. Devuelve
`200` y el evento firmado si se acepta, `400` por sobre o campos ausentes,
`422` por contenido inválido y `401` por token incorrecto. Un fallo de
configuración puede devolver `500`.
El stream requiere `Authorization: Bearer <API_TOKEN_VERIFIER>` y emite
`observation`. Cada suscriptor recibe su copia; admite varios suscriptores.

## Firma del lote

`POST /signBatch` recibe `token`, `sessionId`, `salt`, `patient` (cuenta G) y
`eventKeys` (32 ids de eventos de un mismo dispositivo). Toma las lecturas
(`payload.simple_result`, de 0 a 255) de los eventos que este Verifier verificó y
guarda en memoria; nunca las recibe del cliente. Calcula el commitment Poseidon
del circuito (`verifier_support/poseidon.py`) y firma
`commitment || sessionId || clave de la cuenta G` con la misma clave ed25519 que firma cada evento.
Devuelve `{commitment, signature}` en hexadecimal y `422` si algún evento no es suyo
o el lote no es válido.

## Consumo de Managers

Para recibir eventos desde varios Managers, configura `subscriptions.managers` en `config.json`:

```json
{"subscriptions": {"managers": ["http://manager-a:3003", "http://manager-b:3003"]}}
```

Se usa `API_TOKEN_VERIFIER` como Bearer. Los Managers deben habilitar
`outputStreams.verifiers`. Cada conexión tiene un trabajador y se
reconecta tras cinco segundos. Los eventos aceptados se publican en `/stream`.
Los rechazos se registran y se descartan.

Los resultados se difunden a todos los suscriptores autorizados. Cada consumidor
debe correlacionar `key` con sus propios eventos. El Manager puede consumir
esos resultados mediante `subscriptions.verifiers` y continuar el guardado en Storage.
Los streams no tienen historial ni confirmaciones; usar HTTP y SSE simultáneamente
puede verificar y publicar el mismo evento más de una vez.

## Configuración

El servicio carga `config.env` sin sustituir las variables ya definidas en el entorno.

| Variable o archivo | Uso |
| --- | --- |
| `PORT_VERIFIER` | Puerto HTTP; por defecto `5000`. |
| `API_TOKEN_VERIFIER` | Acceso HTTP/SSE y conexión a los Managers. |
| `MANAGER_PASSWORD` | Clave compartida para comprobar el hash del Manager. |
| `VERIFIER_CONFIG_PATH` | Ruta del JSON; por defecto `config.json` junto al servicio. |
| `MAX_EVENT_AGE_MS` | Antigüedad máxima del evento; por defecto `300000` ms. |
| `MAX_FUTURE_DRIFT_MS` | Desfase futuro permitido; por defecto `30000` ms. |
| `signing_key.json` | Clave ed25519 (JWK) que firma cada evento y cada lote, junto a `verifier.py`. No se versiona: `tools/generate_configs.sh` copia la de `circuits/build/verifier_dev_key.json`, que es la que conoce el contrato. Si falta, se usa una clave temporal. |

La configuración actual comparte clave y token entre Managers; no define
credenciales independientes por Manager. El cálculo del hash está en
`verifier_support/event_auth.py`.

## Pruebas

Desde la raíz, con el entorno descrito en el [README principal](../../README.md):

```sh
./tools/test.sh 'test_verifier_*.py'
./tools/test_integration.sh
```

La integración usa conexiones reales, comprueba la firma ed25519, rechaza eventos
alterados y verifica el dato guardado en Storage.

Las utilidades de este servicio están en `verifier_support/`. No requieren código de otros servicios.

Cada destino también admite `{"url": "http://manager:3003", "token": "..."}` para credenciales propias.

El JSON también admite `server.host`, `server.port`, `keyPath` (ruta relativa
a la carpeta del Verifier). `PORT_VERIFIER` explícito prevalece sobre el puerto JSON.
Varios Managers pueden enviar HTTP al mismo Verifier con su token de acceso;
varios Verifiers pueden suscribirse a cada Manager sin confirmaciones SSE.

## Docker

Desde la raíz del proyecto:

```sh
docker build -t phonendo-verifier apps/verifier
```

[Arranque conjunto, configuración y pruebas](../../deploy/docker/README.md).

`stream.enabled` controla exclusivamente el `/stream` propio (por defecto `true`).
La lista `subscriptions.managers` se consume aunque el stream propio esté deshabilitado.
Deshabilitarlo impide que otros reciban los resultados por SSE.
