# Roadmap de interfaz — Jose, Manolo y Lucia

## Objetivo y alcance

Crear un panel web para ver la red Phonendo, consultar lecturas y errores y,
después, configurar y gestionar sus despliegues. Los servicios actuales siguen
en Python y C++; no hace falta reescribirlos en Rust.

Base propuesta para el panel: **Leptos para la interfaz, Axum para el backend,
SQLite para su inventario y SSE para actualizar el navegador**. Este documento
describe trabajo pendiente, no APIs ya implementadas.

El panel de administración debe apoyar la demo de HackMeridian. No sustituye
la pantalla del caso de uso: paciente con sus lecturas y aseguradora con el
resultado de la sesión y el pago, sin acceso a las lecturas privadas.

## Reparto de responsabilidades

| Persona | Área principal | Entrega a los demás |
| --- | --- | --- |
| **Jose — Linux** | Servicios Phonendo, instrumentación e integración | Endpoints reales, explicación de sus estados y un despliegue reproducible |
| **Manolo — Windows** | Backend del panel e integración con Docker | API unificada, inventario, actualizaciones SSE y acciones de administración |
| **Lucia — Windows** | Interfaz y experiencia de usuario | Mapa, detalle de servicios, lecturas, logs y formularios conectados a la API |

Jose mantiene las reglas del pipeline; Manolo reúne información y ejecuta las
acciones del panel; Lucia presenta los datos y recoge las acciones del usuario.
Los contratos compartidos se acuerdan entre los tres antes de implementarlos.

## Cómo viajan los datos

```text
Navegador (Lucia)
        ↕ API HTTP + SSE del panel
Backend Axum (Manolo)
        ├── Docker: contenedores, imágenes, recursos y logs
        ├── SQLite: despliegues y configuración deseada
        └── Servicios Phonendo (Jose): estado real, conexiones y lecturas
```

El navegador habla con el backend del panel. Este recoge los datos una vez y
los distribuye a las pestañas conectadas. La monitorización no reenvía
observaciones al pipeline ni abre rutas de procesamiento alternativas.

| Dato visible | Fuente real |
| --- | --- |
| Imagen, puertos, contenedor, CPU y RAM | Docker |
| Nodos y conexiones deseadas | Inventario y configuración del despliegue |
| Conexión activa, transporte seleccionado y último fallo | Estado del servicio que gestiona la conexión |
| Dispositivos y sensores conocidos | Reader: `/devices` y `/devices/{id}` |
| Lecturas recientes | Reader: `/stream`, cuando esté habilitado |
| Histórico verificado | Storage; falta una consulta filtrada y paginada |
| Sesión, prueba y pago | Futura integración con Publisher y Stellar |

Un contenedor `running` no demuestra que su servicio funcione. Un dispositivo
listado tampoco demuestra que esté conectado físicamente. La interfaz debe
mostrar por separado configuración, disponibilidad y última actividad conocida.

## Fase 0 — Acordar el contrato y arrancar en paralelo

**Participan los tres.** Primera entrega: ejemplos JSON compartidos y una lista
de rutas, campos y estados. Propuesta de ubicación futura:
`apps/control/contracts/` con esquema y ejemplos, sin credenciales.

Acordar:

- Identidad estable de instancia (`instanceId`), distinta del ID del contenedor;
  para Reader, incluir también su `readerId`.
- Fechas UTC en ISO 8601, unidades de las métricas y campos opcionales.
- Estados de servicio: `unknown`, `healthy`, `degraded`, `offline`.
- Estado de conexión: `configured`, `connecting`, `connected`, `disconnected`,
  `blocked`. Separar `transport` (`http` o `sse`) de ese estado.
- Formato de errores: `code`, `message` y `retryable`; sin tokens ni secretos.
- Ejemplos de funcionamiento normal, servicio caído, datos desactualizados y
  conexión redundante rechazada.

Ejemplo propuesto de conexión:

```json
{
  "sourceId": "reader-01",
  "targetId": "manager-01",
  "reportedBy": "manager-01",
  "transport": "sse",
  "state": "connected",
  "observedAt": "2026-10-25T12:30:00Z",
  "lastSuccessAt": "2026-10-25T12:29:59Z",
  "eventsReceived": 1842,
  "lastError": null
}
```

La flecha representa el flujo de datos; `reportedBy` identifica quién conoce
su estado. En SSE el suscriptor puede ser el destino de la flecha.
En HTTP se informa de la última petición y su resultado, no de una supuesta
conexión permanente.

**Criterio de cierre:** Lucia puede dibujar una pantalla con los ejemplos y
Manolo puede servirlos sin esperar a los endpoints reales de Jose.

## Fase 1 — Panel de observación funcional

### Jose: exponer información real

1. Añadir un contrato común de monitorización a los servicios:

   | Ruta propuesta | Contenido |
   | --- | --- |
   | `GET /info` | Identidad, tipo, versión y capacidades disponibles |
   | `GET /status` | Estado, conexiones, transporte, última actividad y errores |
   | `GET /metrics` | Contadores, cola pendiente, errores y tiempos medidos |

2. Empezar por Manager: ya decide qué transporte se permite y dispone de parte
   del estado necesario. Registrar apertura, cierre, rechazo y resultado HTTP;
   actualizar el estado donde sucede la operación, no reconstruirlo leyendo logs.
3. Instrumentar Reader, Verifier y Storage con el mismo vocabulario. Exponer
   solo información que realmente pueden conocer; usar `unknown` cuando falte.
4. Proporcionar lecturas de prueba mediante el Reader simulado y documentar cómo
   consultar los endpoints existentes. Añadir consulta histórica con filtros y
   límite de resultados si la primera gráfica necesita datos anteriores.
5. Añadir pruebas de estados, concurrencia y errores, conservando las pruebas
   de exclusión HTTP/SSE. Mantener operativo el Compose de integración.

No cambiar la regla ya implementada: Reader conserva el primer transporte
seleccionado hasta reiniciar el Manager; para Verifier y Storage prevalece el
HTTP configurado. Las suscripciones específicas usan `server.publicUrl` y
`X-Phonendo-Service-URL`. La monitorización no deduplica observaciones.

### Manolo: reunir y servir la información

1. Crear el backend Axum con configuración por entorno y un modo de datos
   simulados basado en los ejemplos acordados.
2. Guardar en SQLite despliegues, instancias, direcciones y conexiones deseadas.
   Los valores de secretos no se incluyen en las respuestas del inventario.
3. Implementar adaptadores para consultar servicios y Docker. Un servicio caído
   no debe impedir que el panel muestre los demás.
4. Consultar estado inicialmente cada 2–5 segundos, con timeout. Marcar los
   resultados antiguos como desactualizados y conservar la fecha de observación.
5. Ofrecer al frontend estas rutas propuestas:

   | Ruta del panel | Uso |
   | --- | --- |
   | `GET /api/deployments` | Lista de despliegues |
   | `GET /api/deployments/{id}/topology` | Instantánea de nodos y conexiones |
   | `GET /api/instances/{id}` | Detalle unificado de una instancia |
   | `GET /api/readings?...` | Lecturas autorizadas, filtradas y limitadas |
   | `GET /api/instances/{id}/logs?...` | Logs recientes, limitados y saneados |
   | `GET /api/stream` | Actualizaciones de estado, métricas y lecturas |

6. Mantener una recogida compartida por instancia, no una por pestaña. Acotar
   buffers y frecuencia de actualizaciones. Tras reconectar el navegador,
   enviar una nueva instantánea para recuperar el estado sin exigir replay.
7. Probar timeouts, JSON inválido, Docker no disponible, reconexión SSE y
   separación entre despliegues.

SQLite guarda el inventario del panel; Storage sigue siendo la fuente de los
eventos verificados. No copiar toda su base para alimentar la interfaz.

### Lucia: mapa y detalle de cada nodo

1. Crear la estructura visual: navegación, selector de despliegue y estados de
   carga, vacío, error y desconexión del backend.
2. Construir el mapa con los ejemplos JSON. Los nodos muestran estado y última
   actualización; las conexiones muestran transporte y estado real.
3. Al seleccionar un nodo, mostrar identidad, dirección, contenedor, recursos,
   dispositivos conocidos, última actividad y errores disponibles.
4. Añadir gráfica de lecturas recientes y panel de logs con límite de elementos.
   Diferenciar datos simulados, lecturas capturadas y eventos verificados.
5. Sustituir los ejemplos por la API de Manolo y aplicar sus actualizaciones SSE.
   Tras reconectar, sustituir el estado por la instantánea recibida.
6. Probar navegación, errores y recuperación. No mostrar verde cuando el backend
   desconozca el estado ni inventar tasas o latencias.

Los eventos por segundo se calculan a partir de contadores y tiempo. Un contador
puede reiniciarse al reiniciar el servicio. La latencia solo se muestra cuando
exista una medición con significado acordado, por ejemplo duración de `/verify`.

### Prueba conjunta para cerrar la fase

- Los tres ven el mismo despliegue y sus conexiones reales.
- Una lectura simulada aparece en directo y puede localizarse en Storage tras
  verificarse.
- Al detener un servicio, el panel refleja el fallo; al recuperarlo, actualiza
  su estado sin recargar manualmente la página.
- Una ruta SSE redundante aparece como rechazada, sin procesar por ambos canales.
- Abrir dos pestañas no duplica las suscripciones del backend a Phonendo.
- Ninguna respuesta ni log visible expone tokens o claves privadas.

## Fase 2 — Control básico del despliegue

| Jose | Manolo | Lucia |
| --- | --- | --- |
| Definir configuraciones válidas, puertos, volúmenes y efectos de reiniciar | Integrar acciones Docker y generación de JSON/Compose | Añadir formularios, validación visible y seguimiento de acciones |
| Probar persistencia de Storage tras reinicios | Registrar tareas y sus resultados; devolver un ID de operación | Mostrar pendiente, éxito y error según el resultado real |

Primero: arrancar, detener y reiniciar instancias del despliegue seleccionado.
Después: crear un despliegue a partir de una plantilla validada y editar su
configuración. El formulario genera los JSON que consumen los servicios y el
YAML de Compose; no se introduce otro formato de configuración para Phonendo.

Manolo valida también en backend y limita las acciones a contenedores gestionados
por el panel, identificados mediante etiquetas. El navegador nunca accede al
socket de Docker. Las acciones administrativas requieren autenticación; confirmar
borrados indicando si se conservarán o eliminarán los datos.

**Criterio de cierre:** crear un despliegue de prueba, observarlo, reiniciarlo y
comprobar que la configuración aplicada y los datos persistentes son correctos.

## Fase 3 — Pantalla del caso de uso y conexión con Stellar

Esta entrega tiene prioridad sobre la administración avanzada para la demo de
HackMeridian. Puede prepararse en paralelo a la fase 2 cuando el contrato de
datos de sesión esté acordado.

- **Jose:** coordinar el enlace real con Publisher y la verificación del flujo
  de sesión, prueba y pago. La implementación ZK/Soroban es un bloque de trabajo
  aparte que debe tener responsable y estimación explícitos; el panel no lo crea.
- **Manolo:** exponer estado de sesión, resultado verificado, estado de la
  transacción, importe y enlace al explorador desde fuentes reales. Aplicar el
  control de acceso en backend: la aseguradora no recibe lecturas ni logs privados.
- **Lucia:** crear la vista paciente/aseguradora y el botón de simulación.
  Distinguir prueba generada, transacción enviada, confirmada y fallida.

Mientras falte la integración, usar ejemplos claramente etiquetados como
simulación. No mostrar pagos o transacciones ficticios como confirmados.

**Criterio de cierre:** demo real en testnet con enlace a una transacción y vista
de aseguradora sin datos de pulso. Un selector visual de rol no sustituye la
autorización del backend.

## Fase 4 — Ampliaciones después de la demo básica

Por orden de necesidad: asistente de despliegue con varias instancias, gestión
de imágenes, referencias a secretos y rotación de credenciales, y editor visual
de topología. Mantener el mismo reparto: Jose define restricciones, Manolo
implementa operaciones y Lucia construye la interacción.

Descubrimiento Bluetooth/MQTT, permisos por dispositivo y caducidad de tokens no
son capacidades actuales que baste con dibujar. Requieren diseño e implementación
propios. Tampoco es necesario modificar IDs de observaciones para construir el panel.

## Trabajo desde Windows y Linux

| Modalidad | Qué permite |
| --- | --- |
| Lucia: frontend local con ejemplos o API de Manolo | Avanzar sin Docker ni servicios Phonendo |
| Manolo: Axum y SQLite locales en Windows | Desarrollar API, inventario y SSE sin Docker |
| Compose con contenedores Linux, también en Windows con un motor compatible | Probar backend, Docker y servicios juntos |
| Despliegue compartido en el Linux de Jose | Probar la integración desde los navegadores de los tres |

Para gestionar el Docker del Linux de Jose, ejecutar inicialmente el backend
allí. No hace falta publicar el socket de Docker por la red. Manolo puede probar
su API localmente y desplegar la misma versión en ese entorno.

Jose y Manolo preparan juntos el Compose del panel. Dentro de la red Docker se
usan nombres de servicio; desde Windows o Linux se usa el puerto publicado del
backend. `localhost` dentro de un contenedor identifica a ese contenedor.
Documentar el arranque sin depender de rutas personales ni scripts exclusivos
de una máquina. Lucia y Manolo verifican las instrucciones en Windows.

## Coordinación y primeras tareas

| Orden | Jose | Manolo | Lucia |
| --- | --- | --- | --- |
| 1 | Definir estados y ejemplo real del Manager | Proponer contrato de API y esquema de inventario | Revisar que el contrato cubre mapa y detalle |
| 2 | Implementar `/info` y `/status` del Manager | Servir topología simulada y un SSE funcional | Dibujar mapa y detalle con los ejemplos |
| 3 | Instrumentar el resto y facilitar lecturas | Sustituir simulaciones por adaptadores reales | Conectar API, gráfica y logs |
| 4 | Preparar fallos y recuperación reproducibles | Validar recogida y reconexión | Validar que la UI refleja cada situación |

Dividir los cambios por área para evitar conflictos: Jose en los servicios;
Manolo en el backend del panel; Lucia en el frontend. Como estructura nueva se
propone `apps/control/backend/`, `apps/control/frontend/` y contratos compartidos.
Coordinar cambios en Compose y contratos antes de integrarlos.

Cada entrega incluye cómo arrancarla, qué está implementado y qué sigue simulado.
Probar los comportamientos modificados y hacer una integración conjunta al cerrar
cada fase. Las fases son hitos, no estimaciones de días: ajustar el alcance a la
fecha de la demo antes de empezar administración avanzada.
