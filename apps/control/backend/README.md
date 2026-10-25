# Backend del panel

Servicio Axum que reúne el estado de los servicios Phonendo y de Docker y lo sirve
al frontend por HTTP y SSE. Guarda en SQLite el inventario de despliegues,
instancias y conexiones deseadas. Contrato y ejemplos: [`../contracts`](../contracts/README.md).

## Arranque

Con Rust instalado:

```sh
cargo run                          # datos reales según seed.json
CONTROL_MODE=mock cargo run        # datos simulados, sin servicios ni Docker
cargo test
```

Sin Rust, con Docker, junto al Compose de `deploy/docker` (red `phonendo_default`):

```sh
docker build -t phonendo-control apps/control/backend
docker run --rm --network phonendo_default -p 127.0.0.1:7200:7200 -v /var/run/docker.sock:/var/run/docker.sock:ro phonendo-control
```

La primera vez, si la base está vacía, se carga `seed.json`. Las URL del inventario
son las que usa el backend para llegar a cada servicio: `seed.json` usa los nombres
de la red Docker. Para ejecutarlo fuera de esa red, usa otra semilla con `CONTROL_SEED`
(por ejemplo `http://127.0.0.1:7101`) y borra la base.

## Variables de entorno

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `CONTROL_ADDR` | `127.0.0.1:7200` | Dirección de escucha |
| `CONTROL_DB` | `control.db` | Base SQLite del inventario |
| `CONTROL_SEED` | `seed.json` | Inventario inicial si la base está vacía |
| `CONTROL_MODE` | `live` | `live` o `mock` (datos simulados) |
| `CONTROL_POLL_MS` | `3000` | Intervalo de recogida |
| `CONTROL_TIMEOUT_MS` | `1500` | Timeout por petición a cada servicio |
| `CONTROL_STALE_MS` | 3 × intervalo | Antigüedad a partir de la cual un dato es `stale` |
| `CONTROL_DOCKER` | `auto` | `auto` o `off` |
| `CONTROL_ADMIN_TOKEN` | — | Token de las acciones; sin él quedan desactivadas |
| `CONTROL_PATIENT_TOKEN` | — | Token de la paciente |
| `CONTROL_INSURER_TOKEN` | — | Token de la aseguradora; con alguno de los dos, los datos privados exigen token |
| `CONTROL_CONTRACT_ID` | — | Contrato `adherence`; sin él no se consultan sesiones |
| `CONTROL_STELLAR_RPC` | `https://soroban-testnet.stellar.org` | RPC de Stellar |
| `CONTROL_STELLAR_NETWORK` | `testnet` | Red, para los enlaces a stellar.expert |
| `CONTROL_ASSET` | `XLM` | Activo que paga el contrato (el desplegado paga XLM) |
| `CONTROL_STELLAR_POLL_MS` | `10000` | Intervalo de lectura de eventos |
| `CONTROL_STELLAR_LOOKBACK` | `120000` | Ledgers hacia atrás al arrancar (~7 días, límite del RPC) |

Si una instancia necesita token (p. ej. `/devices` del Reader), el inventario guarda
el nombre de la variable de entorno (`tokenEnv`), nunca su valor, y no se devuelve.

## Rutas

| Ruta | Uso |
| --- | --- |
| `GET /api/deployments` | Lista de despliegues |
| `GET /api/deployments/{id}/topology` | Nodos y conexiones |
| `GET /api/instances/{id}` | Detalle: estado, peers, dispositivos, Docker y conexiones |
| `GET /api/instances/{id}/logs?limit=` | Últimos logs (máx. 200), sin secretos |
| `GET /api/readings?deployment=&deviceId=&readerId=&limit=` | Lecturas verificadas (máx. 500) |
| `POST /api/instances/{id}/actions` | `{"action": "start\|stop\|restart"}`; requiere `Authorization: Bearer <token>`. Responde 202 con la operación |
| `GET /api/operations?deployment=&limit=` | Historial de operaciones, más recientes primero |
| `GET /api/operations/{id}` | Estado de una operación |
| `GET /api/sessions?patient=` | Sesiones cobradas según los eventos del contrato |
| `GET /api/transactions/{hash}` | Estado de una transacción en la red y enlace al explorador |
| `GET /api/me` | Rol y permisos del token |
| `GET /api/stream?deployment=` | SSE: `snapshot` al conectar, `topology` tras cada recogida, `operation` al cambiar una acción y `sessions` con cada cobro nuevo |

## Sesiones y roles

Las sesiones se leen de los eventos `SessionPaid` del contrato mediante el RPC
(`getEvents`): sesión, paciente, importe, transacción y enlace a stellar.expert.
La aseguradora (`CONTROL_INSURER_TOKEN`) solo recibe eso: lecturas, logs y detalle
de instancias responden 403. Tabla completa de permisos en el
[contrato](../contracts/README.md#sesiones-pagos-y-roles). Ejemplo con el contrato
desplegado en testnet:

```sh
CONTROL_CONTRACT_ID=CAPZ2O7LPTRGJ2Q7TTHMCHOKRZ4T7KU5I4E74M2U3YUTC3XONIQDOP2D cargo run
```

## Acciones

Solo se actúa sobre contenedores con estas etiquetas, y la del despliegue debe
coincidir con el de la instancia:

```yaml
labels:
  phonendo.control.managed: "true"
  phonendo.control.deployment: docker-local
```

`deploy/docker/compose.yml` todavía no las tiene: hay que acordar el cambio antes
de añadirlas. Sin ellas, la acción responde 403 `container_not_managed`.

La validación (token, instancia, contenedor, etiquetas y Docker disponible) se hace
antes de aceptar. La operación pasa por `pending` → `running` → `succeeded` o
`failed` y se guarda en SQLite. Solo puede haber una operación en curso por
instancia (409 `operation_in_progress`). Si el backend se reinicia con
operaciones sin terminar, se marcan `failed` con `interrupted`. Tras cada acción
se recoge el estado enseguida para mostrar su efecto real.

## Implementado y pendiente

- Una recogida por despliegue (no por pestaña): `/info` y `/logs` de cada servicio,
  `/devices` del Reader e inspección y recursos del contenedor. Un servicio caído o
  Docker no disponible no impide mostrar el resto.
- Lecturas: se leen de `/raw` de Storage y se filtran aquí, porque Storage aún no
  tiene una consulta filtrada y paginada. Las lecturas en directo por SSE están pendientes.
- `eventsReceived` y el estado `blocked` siguen a `null`/sin uso hasta que los
  servicios expongan contadores y rechazos.
- Roles con tokens fijos por entorno; sin usuarios ni caducidad de tokens.
- Los estados previos al cobro (prueba generada, transacción enviada o fallida)
  necesitan que el Publisher los exponga; hoy solo se ven los cobros confirmados.
- Pendiente de la Fase 2: crear despliegues desde plantillas y editar su
  configuración (generar los JSON de los servicios y el Compose), cuando estén
  definidas las configuraciones válidas.
