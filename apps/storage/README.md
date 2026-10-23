# Storage

Guarda dispositivos y eventos en LevelDB. El Manager consulta aquí los dispositivos
y envía los eventos después de una verificación positiva. Storage no verifica
por sí mismo el hash ni la firma del evento.

## Endpoints

| Ruta | Uso | Acceso actual |
| --- | --- | --- |
| `GET /` | Leer todos los registros. | Sin token. |
| `GET /raw` | Leer todos los registros. | Sin token. |
| `GET /devices/<device_id>` | Consultar un dispositivo. | Bearer o cabecera `X-Storage-Token`. |
| `POST /registerDevice` | Guardar un dispositivo. | `token` en el JSON. |
| `POST /events` | Guardar un evento. | `token` en el JSON. |

Los tokens se comparan con `API_TOKEN_STORAGE`. Los POST reciben
`{"token": "...", "message": {"key": "...", "value": {}}}` y devuelven el
mensaje guardado. Escribir con la misma clave sustituye el valor anterior.
Dispositivos y eventos comparten actualmente el mismo espacio de claves.

## Configuración

`main.py` carga `config.env` y arranca en `PORT_STORAGE` (por defecto `5000`).
`PHONENDO_DB_PATH` indica la ruta de LevelDB; por defecto `/tmp/phonendo_db_path`.
El almacenamiento no consume todavía `/stream/storage` del Manager.

## Pruebas

Desde la raíz, con el entorno descrito en el [README principal](../../README.md):

```sh
./tools/test.sh 'test_storage.py'
./tools/test_integration.sh
```

La integración usa una base de datos temporal y comprueba que el evento Verified
almacenado conserva su contenido y una firma RSA válida.

Las utilidades de este servicio están en `storage_support/`. No requieren código de otros servicios.
