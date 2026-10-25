# Service Network · Canvas View

El operador activo usa estos módulos ES, sin compilación ni dependencias npm.
Se arranca con `./tools/web.sh`; el frontend antiguo de Leptos no interviene.

| Módulo | Responsabilidad |
| --- | --- |
| `models.js` | Servicios y conexiones normalizados; runtime, máquina, organización y tags. |
| `state.js` | Posiciones, selección, viewport y persistencia local por despliegue. |
| `canvas.js` | Montaje y actualización de la vista; nodos DOM estables. |
| `interactions.js` | Arrastre, pan, zoom y teclado mediante Pointer Events. |
| `node.js`, `edge.js` | Tarjetas y geometría de conexiones en coordenadas del mundo. |
| `sidebar.js` | Inspector seleccionado, reutilizando los controles existentes. |
| `configuration/` | Esquemas por servicio, borradores y formulario Visual/JSON con estilos propios. |
| `layout.js` | Auto layout y cálculo de Fit view, sin dependencias del navegador. |
| `api.js` | Cliente del backend local, sin conocimiento del canvas. |
| `index.js` | Adaptador de integración y ciclo de vida. |
| `styles.css` | Clases semánticas del lienzo, nodos, conexiones e inspector. |

`operator.js` aporta la instantánea y las acciones Docker/Reader. El canvas no
conoce URLs de administración ni credenciales. Para otro backend o despliegue,
cambia ese adaptador y su `storageKey`, no los componentes de interacción.
`machineId`, `runtime`, `organization` y `tags` permiten ampliar el modelo a
máquinas remotas y grupos; no implican que esas operaciones estén implementadas.

Los repintados del operador conservan el elemento raíz del canvas. El controlador
actualiza nodos por ID y no recalcula posiciones al recibir datos. Durante un
gesto se aplaza el repintado global. Los listeners y el ResizeObserver se liberan
al desmontar el controlador.

Uso: arrastrar un nodo para colocarlo; arrastrar el fondo o mantener Espacio para
mover el lienzo; rueda o botones +/- para zoom. Las flechas del teclado mueven el
nodo enfocado (Shift amplía el paso). Auto layout reorganiza y Fit view encuadra.
Las conexiones representan relaciones configuradas, no confirmaciones de entrega.

El inspector edita una misma configuración en modo Visual o JSON y conserva los
campos adicionales. Reader aplica cambios en directo; los otros contenedores
gestionados se reinician al guardar. Para servicios externos solo genera un archivo.
Los borradores quedan en memoria y no se guardan secretos en localStorage.

Pruebas de geometría, persistencia, modelo y API, sin instalar paquetes:

```sh
cd apps/web
npm test
```
