# Panel de observación · frontend

Primera entrega de la parte de Lucía del `ROADMAP_UX.md`. Interfaz Leptos en
modo CSR (Rust compilado a WebAssembly), independiente del backend y de los
servicios Phonendo. Todo el contenido está en español.

El diseño sigue el mockup aprobado de **detalle inferior**: tabla de servicios y
logs a la izquierda, grafo interactivo a la derecha y detalle del nodo debajo.
La paleta combina azul y amarillo sobre un fondo oscuro.

## Arranque local

Requisitos: Rust estable actualizado y Trunk. En Windows, Rust necesita las
herramientas de compilación de su plataforma; también se puede usar el toolchain
GNU con sus herramientas de enlace. No hace falta Docker para este frontend.

Desde la raíz del repositorio:

```powershell
rustup target add wasm32-unknown-unknown
cargo install --locked trunk --version 0.22.0
cd apps/control/frontend
trunk serve
```

Abrir `http://127.0.0.1:8080`. Trunk recompila la interfaz al editarla.
La configuración de desarrollo está en `Trunk.toml`; no requiere variables de
entorno ni credenciales. `trunk build --release` genera `dist/`, ignorado por Git.

En este equipo también se han preparado herramientas portables en la carpeta
ignorada `.run/frontend-tools/`. Para utilizarlas desde la raíz, sin cambiar el
PATH de Windows:

```powershell
.\apps\control\frontend\dev.ps1
# Pruebas o compilación, sin arrancar el servidor:
.\apps\control\frontend\dev.ps1 test
.\apps\control\frontend\dev.ps1 build
```

Las herramientas portables no forman parte del repositorio; en otros equipos
se pueden utilizar Rust y Trunk instalados normalmente. El script conserva el
entorno de la consola al terminar.

Esta entrega se ha comprobado con Rust 1.99.1, Trunk 0.22.0 y Leptos 0.8.20.
En este equipo las herramientas portables incluyen también LLVM-MinGW y
wasm-bindgen para completar la compilación en Windows.

## Qué se puede probar

- Seleccionar servicios desde la tabla o el grafo; ambas selecciones se sincronizan.
- Ver flechas de Reader a Manager y de Manager a Verifier y Storage, con su
  transporte y estado. La geometría se adapta al ancho de la ventana.
- Seleccionar un nodo y consultar identidad, dirección configurada, actividad,
  dispositivos conocidos y errores. Recursos no medidos: «No disponible».
- Distinguir la disponibilidad del servicio del estado de su contenedor.
- Desplegar la información de una conexión: transporte, estado, informante,
  fechas y último error. HTTP representa la última petición, no un canal abierto.
- Cambiar el escenario: guardado pendiente de reintento, normal, Storage sin respuesta, datos antiguos, SSE
  redundante rechazada, estado desconocido, carga, vacío, error o desconexión.
- Recuperar el ejemplo normal después de un error y cambiar a un despliegue vacío.
- Consultar una gráfica y sus valores accesibles en tabla. Son lecturas
  sintéticas, no eventos capturados ni verificados; no hay datos de pacientes.
- Ver logs del nodo seleccionado y de operaciones relacionadas, con un máximo
  de 50 elementos, ordenados del más reciente al más antiguo. «Ver todos» recupera
  los logs de todas las instancias; seleccionar otro nodo vuelve a filtrarlos.
- Desplegar cada log para consultar código, detalle, informante, fecha completa
  e instancias relacionadas.

El ejemplo inicial representa Storage degradado y un guardado pendiente de
reintento. Los otros escenarios están en «Escenarios de demostración», al final
de la pantalla. Las lecturas y su tabla se encuentran dentro del detalle del Reader.

Publisher ya tiene implementación en el proyecto, pero esta instantánea no dispone
de datos de su monitorización. Se muestra «Sin datos», sin deducir conexiones,
actividad ni pagos. Su estado desconocido no implica que esté parado.

La instantánea y sus fechas son fijas, no mediciones en directo. Los escenarios
son controles manuales para revisar la interfaz. En los casos de datos antiguos
y backend desconectado se conserva la instantánea, pero se muestra disponibilidad
desconocida en lugar de verde. La gráfica admite como máximo 32 puntos.

## Datos e integración pendiente

`examples/topology.json` contiene el ejemplo local. `src/lib.rs` define sus tipos
y aplica los escenarios; `src/app.rs` presenta los datos. `src/graph.mjs` mide los
nodos y sitúa las flechas con `ResizeObserver` y `MutationObserver`, liberados al
desmontar el grafo. Los estados y la selección se mantienen en Leptos.
Es una propuesta de
consumo del frontend, **no un contrato de API acordado entre los tres**.

Campos principales para revisar con Manolo y Jose:

| Objeto | Campos |
| --- | --- |
| Instantánea | `deploymentId`, `name`, `simulated`, `observedAt`, `stale` |
| Nodo | `instanceId`, `kind`, `status`, `readerId`, dirección, contenedor, actividad, recursos opcionales, dispositivos y error |
| Conexión | `sourceId`, `targetId`, `reportedBy`, `transport`, `state`, fechas, `eventsReceived`, `lastError` |
| Error | `code`, `message`, `retryable` |
| Log | `instanceId`, `at`, `level`, `message`, `relatedInstanceIds`, `code`, `detail` |

Fechas completas en UTC ISO 8601; CPU en porcentaje y memoria en MB cuando se
midan. `null` significa que no hay información. Las horas de las lecturas del
ejemplo pertenecen al día de la instantánea y están en UTC.

Después de acordar el contrato, sustituir los ejemplos por las rutas propuestas
de Manolo (`/api/deployments`, topología, detalle, lecturas, logs y `/api/stream`).
La integración deberá reemplazar la instantánea al reconectar y cancelar la
suscripción al cerrarse; ahora no se abre ninguna petición HTTP ni SSE.
El navegador no accede al socket Docker ni a las credenciales de los servicios.

Pendientes: API real, SSE, detección automática de antigüedad, gráfica e histórico
reales, acciones administrativas y vista paciente/aseguradora. No se muestran
pruebas ZK, pagos ni transacciones ficticias como confirmados.

## Comprobaciones

Desde esta carpeta:

```powershell
cargo test
node --test tests/graph.test.mjs
trunk build
```

Las pruebas Rust verifican referencias de la topología, estados desconocidos ante
datos antiguos, independencia entre contenedor y servicio, rechazo SSE con HTTP
conservado, relaciones entre logs y límites de logs y lecturas. Las pruebas de
geometría necesitan Node.js 22 o superior y comprueban extremos de flechas,
ramas verticales, separación de HTTP/SSE paralelos y etiquetas sin solapamiento;
no requieren `npm install`.
La compilación con Trunk comprueba también
los componentes de Leptos para WebAssembly.

Revisión manual: recorrer los diez escenarios, seleccionar los cinco nodos desde
el grafo y la tabla, abrir los logs y las conexiones, consultar las lecturas del
Reader y probar recuperación, teclado y vista estrecha. Los ejemplos se sirven
localmente; no hay publicación web.
