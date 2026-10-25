# Storage

Guarda eventos en LevelDB. El Manager envía los eventos después de una
verificación positiva. Storage no verifica
por sí mismo el hash ni la firma del evento.

## Endpoints

| Ruta | Uso | Acceso actual |
| --- | --- | --- |
| `GET /` | Leer todos los registros. | Sin token. |
| `GET /raw` | Leer todos los registros. | Sin token. |
| `GET /stream` | Eventos guardados, en vivo. | Bearer `API_TOKEN_STORAGE`. |
| `POST /events` | Guardar un evento. | `token` en el JSON. |

Los tokens se comparan con `API_TOKEN_STORAGE`. Los POST reciben
`{"token": "...", "message": {"key": "...", "value": {}}}` y devuelven el
mensaje guardado. Escribir con la misma clave sustituye el valor anterior.
Dispositivos y eventos comparten actualmente el mismo espacio de claves.

## Configuración

`main.py` carga `config.env` y arranca en `PORT_STORAGE` (por defecto `5000`).
`PHONENDO_DB_PATH` indica la ruta de LevelDB; por defecto `/tmp/phonendo_db_path`.
`STORAGE_CONFIG_PATH` selecciona el JSON (por defecto `config.json` junto al servicio).
El JSON permite configurar `server.host`, `server.port`, `databasePath`, `token`
y las conexiones. Las variables de entorno ya definidas prevalecen en puerto,
ruta de base de datos y token.

Para consumir varios Managers por SSE:

```json
{
  "subscriptions": {"managers": [
    {"url": "http://manager-a:3003", "token": "token-a"},
    {"url": "http://manager-b:3003", "token": "token-b"}
  ]},
  "stream": {"enabled": true}
}
```

Se suscribe a `/stream/storage` de cada Manager, guarda solo mensajes `Verified`
con `verifierSign` y reconecta cada conexión por separado. No espera confirmaciones
ni existe historial SSE. Cada Manager debe habilitar `outputStreams.storages`.
Si una entrada no define token, usa el token local de Storage.

El mismo Storage recibe HTTP de varios Managers con su token de acceso.
Un Manager puede enviar a varios Storages, por HTTP o mediante varios suscriptores SSE.

## Pruebas

Desde la raíz, con el entorno descrito en el [README principal](../../README.md):

```sh
./tools/test.sh 'test_storage.py'
./tools/test_integration.sh
```

La integración usa una base de datos temporal y comprueba que el evento Verified
almacenado conserva su contenido y una firma RSA válida.

Las utilidades de este servicio están en `storage_support/`. No requieren código de otros servicios.

## Docker

Desde la raíz del proyecto:

```sh
docker build -t phonendo-storage apps/storage
```

[Arranque conjunto, configuración y pruebas](../../deploy/docker/README.md).

## Separación de capacidades SSE

`stream.enabled` habilita el `/stream` **de Storage**: emite cada evento después de
escribirlo, tanto si llegó por HTTP como por una suscripción. No ofrece historial.
`subscriptions.managers` controla de forma independiente el consumo de
`/stream/storage` de Managers. Puede consumir aunque su stream propio esté apagado,
o exponer su stream sin suscribirse a nadie. `outputStreams` no se utiliza en
Storage; su salida general es `/stream`.

Storage recibe eventos sin altas previas de dispositivos y gestiona su propia base de datos.
