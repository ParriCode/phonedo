# Phonendo Reader

Reader de Phonendo. El core vive en C++ portable y los runtimes quedan separados por plataforma.

El flujo actual está simplificado: la identidad va por `device_id`, no por MAC, y el `serial_manager` solo acepta un formato de mensaje.

## Estructura

```text
apps/reader/
├── core/
│   ├── src/
│   └── bindings/
├── linux/
│   ├── main.py
│   ├── cpp_reader_core.py
│   ├── devices_and_sensors.json
│   ├── bluetooth_manager/
│   └── serial_manager/
└── arduino/
    ├── platformio.ini
    └── src/
```

## Flujo

1. `Reader` carga `config.env`.
2. Crea `ReaderCore`.
3. Carga `devices_and_sensors.json`.
4. Registra los `Device` y `Sensor` configurados.
5. Arranca los managers activos.
6. `SerialDeviceManager` detecta puertos y lee líneas.
7. Cada línea JSON válida se convierte en `Observation`.
8. `Reader` busca o crea el `Device` y `Sensor`.
9. `ReaderCore` genera la observación final y la envía al Manager.

## Configuración

Ejemplo:

```json
{
  "serial": {
    "glob": "/dev/rfcomm*",
    "baudrate": 9600,
    "read_timeout": 1.0,
    "poll_seconds": 1.0,
    "reconnect_seconds": 2.0
  },
  "devices": [
    {
      "comm": "/dev/rfcomm1",
      "device_id": "prueba2",
      "allow_conflicts": false
    }
  ],
  "sensors": [
    {
      "sensor_id": "temp1",
      "device_id": "prueba2",
      "observable_property": "temperatura",
      "procedure": "termorreceptor",
      "feature_of_interest": "patient-001",
      "unit": "CELSIUS",
      "allow_conflicts": false
    }
  ]
}
```

### `serial`

- `glob`: patrón de puertos a descubrir. Por defecto `/dev/rfcomm*`.
- `ports`: lista opcional de puertos permitidos. Si se define, filtra los puertos encontrados por `glob`.
- `baudrate`: velocidad del puerto serie.
- `read_timeout`: timeout de `readline()`.
- `poll_seconds`: cada cuánto se revisa si hay puertos nuevos.
- `reconnect_seconds`: espera antes de reintentar tras error de lectura.

### `devices`

- `device_id`: identificador lógico del dispositivo.
- `comm` o `com`: puerto serie asociado, por ejemplo `/dev/rfcomm1`.
- `allow_conflicts`: permite aceptar un `device_id` distinto al configurado para ese puerto.
- `static`: si es `true`, no permite sensores nuevos en ese dispositivo.

### `sensors`

- `sensor_id`: identificador del sensor.
- `device_id`: opcional. Si se define, el sensor queda ligado al device y al puerto configurado para ese device. Si no se define, el sensor es portable y puede llegar por cualquier puerto.
- `observable_property`: propiedad observada.
- `procedure`: procedimiento de medición.
- `feature_of_interest`: entidad observada.
- `unit`: unidad opcional.
- `allow_conflicts`: permite aceptar un `sensor_id` distinto al configurado para ese puerto.

## Formato De Mensaje Serie

Se aceptan dos entradas:

- Valor crudo en una línea.
- JSON con claves `snake_case`.

Si llega una línea que no es JSON, se interpreta automáticamente como `value`.

Valor crudo:

```text
83.4
```

Equivale a:

```json
{"value":"83.4"}
```

Mensaje mínimo:

```json
{"value":"45.3"}
```

Mensaje completo:

```json
{
  "device_id": "prueba2",
  "sensor_id": "temp1",
  "value": "45.3",
  "observable_property": "temperatura",
  "procedure": "termorreceptor",
  "feature_of_interest": "patient-001",
  "unit": "CELSIUS"
}
```

Claves permitidas:

```text
device_id
sensor_id
value
observable_property
procedure
feature_of_interest
unit
```

En JSON, todo lo demás se descarta. No se aceptan:

- `deviceId`, `sensorId`, `observableProperty`, etc.
- `sensor:valor`.
- JSON sin `value`.
- claves extra.

## Cómo Funciona `serial_manager`

`SerialDeviceManager` tiene dos bucles:

- `_watch_loop()`: descubre puertos periódicamente con `glob`.
- `_reader_loop(port)`: abre cada puerto y espera líneas con `serial_port.readline()`.

Descubrimiento:

```python
ports = sorted(glob.glob(self.port_glob))
```

Lectura:

```python
raw = await asyncio.to_thread(serial_port.readline)
```

Esto significa:

- El descubrimiento de puertos es por polling cada `poll_seconds`.
- La lectura de datos no es polling; una vez abierto el puerto, queda esperando una línea.
- Si el puerto aparece y manda datos antes de que el watcher lo abra, esos primeros datos podrían perderse.

Cuando llega una línea:

```text
bytes -> JSON -> Observation -> Reader.handle_serial_data()
```

## Sensores Portables Y Conflictos

El parser primero asigna contexto usando el puerto, el `sensor_id` recibido y la configuración.

Un sensor sin `device_id` es portable:

```json
{
  "sensor_id": "temp1",
  "observable_property": "temperatura",
  "procedure": "termorreceptor"
}
```

Puede llegar por `/dev/rfcomm0`, `/dev/rfcomm1` o cualquier puerto escuchado. Si además es el único sensor portable configurado, también puede aceptar valores crudos como:

```text
45.3
```

Un sensor con `device_id` queda ligado al puerto del device:

```json
{
  "sensor_id": "temp1",
  "device_id": "prueba2",
  "observable_property": "temperatura",
  "procedure": "termorreceptor"
}
```

Si `prueba2` está configurado en `/dev/rfcomm1`, ese sensor no se acepta por `/dev/rfcomm9`.

Después de asignar el contexto, el parser compara el mensaje con la configuración.

Si el puerto está configurado con:

```json
{
  "comm": "/dev/rfcomm1",
  "device_id": "prueba2",
  "allow_conflicts": false
}
```

Y llega:

```json
{"device_id":"otro","value":"45.3"}
```

La medición se descarta.

Para permitirlo:

```json
{"allow_conflicts": true}
```

Para sensores pasa lo mismo con `allow_conflicts` dentro del sensor configurado. Internamente se guarda como política para `sensor_id`, semántica y unidad.

## Fallback

Si falta `device_id` en el mensaje:

1. Se usa el `device_id` configurado para el puerto.
2. Si no hay configuración, `Reader` usa su `reader_id`.

Si falta `sensor_id`:

1. Se usa el `sensor_id` configurado para el puerto.
2. Si no hay sensor único configurado para ese puerto, se usa el nombre del puerto.

Si el `Device` o el `Sensor` no existen y el Reader no está en modo `static`, se crean con los metadatos disponibles.

## Uso

Desde la raíz del repo:

```bash
python3 apps/reader/linux/main.py
```

Con configuración explícita:

```bash
python3 apps/reader/linux/main.py --config apps/reader/linux/devices_and_sensors.json
```

Con identificador de Reader:

```bash
python3 apps/reader/linux/main.py --reader-id reader-1
```

Modo estático:

```bash
python3 apps/reader/linux/main.py --static
```

En modo estático no se crean dispositivos ni sensores que no estén en la configuración.

## Variables De Entorno

Se cargan desde `apps/reader/config.env`.

- `API_TOKEN_MANAGER`: token usado al enviar eventos.
- `INTERNAL_URL_MANAGER`: URL base del Manager.
- `PHONENDO_LOGS_DIR`: carpeta de logs.
- `PHONENDO_VERBOSE`: logs detallados si es verdadero.
- `PHONENDO_LOGGING`: activa/desactiva logging.
- `PHONENDO_DEV`: modo dev del logger.

## BLE

`bluetooth_manager` queda separado del flujo serie. Solo escanea BLE si se configura explícitamente:

```json
{
  "bluetooth": {
    "ble": {
      "enabled": true,
      "scan_timeout_seconds": 2.0,
      "sleep_seconds": 0.5
    }
  }
}
```

También emite `Observation`; no hay clases paralelas tipo `BluetoothObservation`.

## Observaciones

La única clase de medición que circula por el Reader es:

```python
reader_core.observation.Observation
```

Campos:

- `observable_property`
- `simple_result`
- `phenomenon_time`
- `feature_of_interest`
- `procedure`
- `device_id`
- `sensor_id`
- `unit`
- `observation_id`

No se usa MAC para identificar dispositivos. La identidad se resuelve por `device_id`.

## Ejemplo Con Arduino/RFCOMM

Si Arduino manda por Bluetooth serie a `/dev/rfcomm1`, debe enviar una línea JSON terminada en salto de línea:

```text
36.7
```

O como JSON mínimo:

```text
{"value":"36.7"}
```

O completa:

```text
{"device_id":"prueba2","sensor_id":"temp1","value":"36.7","observable_property":"temperatura","procedure":"termorreceptor","feature_of_interest":"patient-001","unit":"CELSIUS"}
```

El salto de línea importa porque la lectura se hace con `readline()`.
