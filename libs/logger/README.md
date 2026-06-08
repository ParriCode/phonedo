# Logger Python

Logger sencillo para los servicios Python de Phonendo.

La librería expone una única clase `Logger`. Funciona como singleton estático: se inicializa una vez al arrancar el servicio y después se usa desde cualquier punto con métodos de clase.

## Inicialización

```python
from logger import Logger

Logger.init(
    logs_dir="logs/dev",
    service="manager",
    verbose=False,
    logging=True,
    dev=False,
)
```

El logger no carga variables de entorno. El servicio debe cargar su configuración y pasar los valores ya resueltos:

```python
import os

def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

Logger.init(
    logs_dir=os.getenv("PHONENDO_LOGS_DIR", "logs/services"),
    service="manager",
    verbose=env_bool("PHONENDO_VERBOSE", False),
    logging=env_bool("PHONENDO_LOGGING", True),
    dev=env_bool("PHONENDO_DEV", False),
)
```

Variables habituales que puede cargar cada servicio:

```env
PHONENDO_VERBOSE=false
PHONENDO_LOGGING=true
PHONENDO_DEV=false
```

## Comportamiento

`verbose` controla la consola:

- `true`: imprime los logs por consola.
- `false`: no imprime nada por consola.

Cuando la consola está activa, solo el valor del campo `level` se colorea:
`DEBUG` en cian, `INFO` en verde, `WARNING` en amarillo y `ERROR` en rojo.
Los ficheros de log no incluyen colores y siguen siendo JSON Lines limpio.

`logging` controla los archivos:

- `true`: guarda los logs en archivo.
- `false`: no guarda nada.

`dev` controla los logs marcados como desarrollo:

- Si una llamada tiene `dev=True`, solo se emite si el logger se inicializó con `dev=True`.
- Si `dev` está desactivado, esos logs no se imprimen ni se guardan.

Los logs se escriben en formato JSON Lines, un JSON por línea, en:

```text
<logs_dir>/<service>.log
```

## Uso

```python
Logger.info("device_registered", deviceId="esp8266-device-01")
Logger.warning("device_not_registered", deviceId="esp8266-device-01")
Logger.error("storage_request_failed", error="Connection refused")
```

Logs de desarrollo:

```python
Logger.debug("request_body", dev=True, body=body)
Logger.info("manager_env_loaded", dev=True, keys=["PORT_MANAGER"])
```

`Logger.debug(...)` usa `dev=True` por defecto.

Logs de peticiones:

```python
Logger.request(
    "POST",
    "/registerDevice",
    200,
    deviceId="esp8266-device-01",
    readerId="reader-esp8266-01",
)
```

## Ejemplo de salida

```json
{"ts":"2026-05-25T19:50:12.123456+00:00","level":"INFO","service":"manager","message":"device_registered","deviceId":"esp8266-device-01"}
```

## Notas

No se deben registrar tokens, contraseñas ni secretos. Si se registran cuerpos de petición en modo desarrollo, hay que filtrar previamente los campos sensibles.
