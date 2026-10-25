# Contrato del panel

Propuesta de Fase 0 (pendiente de acordar con Jose y Lucia). Son ejemplos de las
respuestas del backend (`apps/control/backend`). Los tests del backend comprueban
que encajan con sus tipos, así que un cambio aquí debe ir acompañado del cambio en
`src/model.rs`.

## Convenciones

- Campos en `camelCase`. Fechas en UTC, ISO 8601 con milisegundos.
- Los campos opcionales se envían como `null`, no se omiten.
- `simulated: true` indica datos del modo simulado (`CONTROL_MODE=mock`).
- Errores: `{ "code", "message", "retryable" }`, sin tokens ni secretos.
- `instanceId` identifica la instancia en el inventario; no es el ID del contenedor.

## Estados

| Campo | Valores |
| --- | --- |
| Servicio `status` | `unknown` (aún sin consultar), `healthy`, `degraded` (responde, pero no cumple el contrato), `offline` (sin respuesta o timeout) |
| `stale` | `true` si la última observación supera `CONTROL_STALE_MS`; se conserva `observedAt` |
| Conexión `state` | `configured`, `connecting`, `connected`, `disconnected`, `blocked` |
| `transport` | `http` o `sse`, separado del estado |

HTTP no mantiene una conexión: si el servicio declara el destino en `/info` se
muestra `configured`. SSE activo se muestra `connected`. `desired: false` indica
una conexión declarada por un servicio que no figura en el inventario.

## Ejemplos

| Archivo | Ruta |
| --- | --- |
| `deployments.json` | `GET /api/deployments` |
| `topology-normal.json` | `GET /api/deployments/{id}/topology`, todo funciona |
| `topology-service-down.json` | Verifier caído |
| `topology-stale.json` | Datos desactualizados |
| `topology-redundant-rejected.json` | SSE redundante rechazado (409) |
| `instance.json` | `GET /api/instances/{id}` |
| `logs.json` | `GET /api/instances/{id}/logs?limit=` |
| `readings.json` | `GET /api/readings?deployment=&deviceId=&readerId=&limit=` |
| `operation.json` | `POST /api/instances/{id}/actions`, `GET /api/operations/{id}` |
| `error.json` | Cualquier error |

`GET /api/stream?deployment=` emite `snapshot` al conectar (y al reconectar) y
`topology` tras cada recogida, ambos con el cuerpo de `topology-*.json`, y
`operation` con el cuerpo de `operation.json` cada vez que cambia una acción.

Estados de una operación: `pending`, `running`, `succeeded`, `failed`. La interfaz
muestra el resultado según `status` y `error`, sin suponer éxito al enviar.

El estado `blocked` está previsto, pero hoy `/info` no informa de los rechazos:
el backend no lo genera hasta que los servicios lo expongan.
