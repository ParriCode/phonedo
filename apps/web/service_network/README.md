# Service Network · Canvas View

Lógica del lienzo del operador, sin React ni dependencias del navegador. Los
componentes que la pintan están en `src/components/canvas` (ver el
[README de la web](../README.md)).

| Módulo | Responsabilidad |
| --- | --- |
| `models.js` | Servicios y conexiones normalizados; runtime, máquina, organización y tags. |
| `state.js` | Posiciones, selección, viewport y persistencia local por despliegue. |
| `layout.js` | Auto layout y cálculo de Fit view. |
| `edge.js` | Geometría de las conexiones en coordenadas del mundo. |
| `api.js` | Cliente del backend local, sin conocimiento del canvas. |
| `styles.css` | Clases semánticas del lienzo, nodos, conexiones e inspector. |

En React, `ServiceCanvas` guarda un `CanvasState` por montaje: los datos que llegan
del sondeo no recalculan posiciones y los gestos no dependen del repintado global.
`useCanvasInteractions` enlaza los Pointer Events y los libera al desmontar.
`machineId`, `runtime`, `organization` y `tags` permiten ampliar el modelo a
máquinas remotas y grupos; no implican que esas operaciones estén implementadas.

Uso: arrastrar un nodo para colocarlo; arrastrar el fondo o mantener Espacio para
mover el lienzo; rueda o botones +/- para zoom. Las flechas del teclado mueven el
nodo enfocado (Shift amplía el paso). Auto layout reorganiza y Fit view encuadra.
Las conexiones representan relaciones configuradas, no confirmaciones de entrega.

Pruebas de geometría, persistencia, modelo y API (incluidas en `npm test`):

```sh
cd apps/web
node --test service_network/tests/*.test.js
```
