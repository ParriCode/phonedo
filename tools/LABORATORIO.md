# Laboratorio Docker

Interfaz de escritorio para crear contenedores de Reader, Manager, Verifier y
Storage, ver puertos/configuración/logs y probar dispositivos y sensores.

## Arranque

Necesitas Docker en ejecución y accesible desde tu usuario, Python con Tkinter
y una sesión gráfica. Desde la raíz:

```sh
./tools/lab.sh
```

El script utiliza `.venv/bin/python` por defecto; también puedes ejecutar
`python3 tools/lab.py`, ya que la interfaz utiliza la biblioteca estándar.
Si falta Tkinter, el paquete de Debian/Ubuntu es `python3-tk`.
No necesitas instalar las dependencias de los servicios en tu máquina:
se instalan al construir las imágenes. La primera construcción tarda más.

## Recorrido de prueba

1. Crea **Storage** en el puerto local **7104**, nombre **storage-1**.
2. Crea **Verifier** en **7103**, nombre **verifier-1**.
3. Crea **Manager** en **7102**, nombre **manager-1**.
4. Crea **Reader** en **7101**, nombre **reader-1**.
5. Selecciona el Reader y abre **Dispositivos y sensores**.
6. Introduce dispositivo, sensor, propiedad y unidad, y pulsa **Añadir dispositivo/sensor**.
7. Envía un valor JSON manual (`23.5`, `true`, `"texto"`) o una serie
   como `[20, 21, 22]` con intervalo en segundos. **Iniciar serie** la repite
   circularmente hasta **Parar serie**.

**Ver dispositivos** actualiza la tabla de dispositivos y sensores. Puedes añadir
varios sensores a un dispositivo, y borrar sensores o dispositivos. La pestaña
**Logs** muestra los mensajes de todos los contenedores con el nombre de su instancia.
**Abrir en navegador** abre la consulta del servicio seleccionado; en Storage
muestra los datos guardados.

## Puertos y conexiones

La tabla distingue **puerto local**, **puerto contenedor** y **URL Docker**.
Por ejemplo, el Manager publicado en `http://127.0.0.1:7102` recibe conexiones de
otros contenedores mediante `http://manager-1:3003`.
Dentro de los JSON usa las **URL Docker** de la tabla para conectar servicios.
`127.0.0.1` dentro de un contenedor apunta a ese mismo contenedor.

Todas las instancias de la ventana comparten una red Docker propia. Al crear una
configuración, las URLs se proponen a partir de las instancias ya creadas. Puedes
editarlas para configurar relaciones N a N. Para más instancias cambia el nombre
y el puerto local; el puerto interno puede repetirse entre contenedores.

Los servicios usan credenciales de laboratorio y una clave compartida propia de
la sesión. El Verifier monta `apps/verifier/keys.json` en lectura. Ningún
`config.env` del proyecto se copia o modifica.

## Parar, pausar y reanudar

- **Pausar** congela el contenedor y conserva el proceso en memoria.
- **Reanudar / Arrancar** continúa un contenedor pausado o arranca uno parado.
- **Parar** detiene el servicio y conserva su contenedor, configuración y datos
  durante la sesión. Storage conserva su base de datos; Reader recupera sus
  dispositivos, sensores y series configuradas. Las series reinician su secuencia.
  La cola volátil del Manager se pierde al parar su proceso.

Las operaciones Docker se ejecutan en segundo plano para que la ventana siga
respondiendo. Los estados se actualizan periódicamente. El JSON se edita antes de
crear un contenedor; seleccionar una instancia muestra el utilizado al arrancar.

Al cerrar la ventana se eliminan exclusivamente los contenedores, red y datos
temporales creados por esa sesión. No gestiona contenedores Compose ajenos.
Publisher sigue pendiente y no se incluye.

Los controles del Reader pertenecen al laboratorio: este monta un pequeño
adaptador con su endpoint `/_lab/command`. El Reader normal y su Dockerfile
conservan su funcionamiento habitual.

## Prueba automática

Con el entorno de pruebas del proyecto preparado:

```sh
.venv/bin/python -m pytest tests/docker -v
```

Arranca los cuatro servicios reales, comprueba envío manual y periódico,
pausa/reanudación, recuperación del Reader y persistencia de Storage al parar
y arrancar. Con una sesión gráfica también prueba los botones de la interfaz;
sin pantalla esa prueba se omite. Al terminar elimina sus contenedores y red.

## Opciones de stream del JSON

- `stream.enabled`: expone el stream propio.
- `subscriptions`: listas de streams consumidos; no dependen del stream propio.
- `outputStreams`: salidas específicas del Manager (`verifiers`, `storages`).
- `services`: destinos HTTP.

Para Storage, sus Managers SSE van en `subscriptions.managers`;
para Manager, las fuentes van en `subscriptions.readers`, `verifiers` y `storages`.
