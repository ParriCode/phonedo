# Phonendo con Docker

Los cinco servicios se construyen y arrancan con Compose.
Los archivos `config.env`, las claves y los entornos virtuales se excluyen de las
imágenes mediante `.dockerignore`. Referencia: [contexto de construcción de Docker](https://docs.docker.com/build/concepts/context/).

## Arrancar el ejemplo completo

Desde la raíz del proyecto, con Docker y Docker Compose instalados:

```sh
docker compose -f deploy/docker/compose.yml up --build -d --wait
```

El ejemplo usa credenciales de demostración y un Reader simulado (`"demo"`): 32 lecturas
de pulso (95-120 BPM) y luego 32 de temperatura de transporte (2-8 °C). El Publisher
consume el SSE del Manager y prepara lotes de 32.

## Cobro real en testnet (demo preconfigurada)

**SOLO TESTNET / CLAVES DE DEMOSTRACIÓN.** El repositorio lleva todo lo necesario para
cobrar sin pasos manuales: la cuenta `phonendo` (publisher, admin de los contratos y
fuente de despliegue), la clave Ed25519 del Verifier (`deploy/demo/verifier_demo_key.json`),
los artefactos del circuito (`circuits/build/`) y dos contratos desplegados y fondeados con
XLM nativo, uno de rehabilitación y otro de cadena de frío. Los ids están en
`deploy/docker/publisher.json`: `contracts` por `verifierId` (rehabilitación) y `devices`
por dispositivo (cadena de frío). Esas claves son públicas y no valen nada; cualquiera
puede gastar los fondos de testnet de esa cuenta.

Tras `up --build -d --wait`, el Reader simulado emite los dos casos y el Publisher cobra
cada uno. Comprueba el cobro con `curl http://127.0.0.1:7105/info` o buscando
`publisher_session_paid` en `docker compose ... logs publisher`; el log trae el enlace de
la transacción en Stellar Expert. Para usar tu propia cuenta, crea `deploy/docker/.env`
(ignorado por git); tiene prioridad sobre la de demostración:

```sh
printf 'STELLAR_SECRET_KEY=%s\nSTELLAR_SOURCE=%s\n' "$(stellar keys show alex)" alex > deploy/docker/.env
```

Con tu cuenta tendrás que desplegar tus contratos (`deploy/demo/desplegar_demo.sh`).
El Reader arranca cuando el Publisher ya escucha, para que no pierda lecturas; si
repites la demo, reinícialo: `docker compose -f deploy/docker/compose.yml restart reader`.

| Servicio | Puerto local | Comprobación |
| --- | --- | --- |
| Reader | 7101 | `http://127.0.0.1:7101/health` |
| Manager | 7102 | `http://127.0.0.1:7102/` |
| Verifier | 7103 | `http://127.0.0.1:7103/` |
| Storage | 7104 | `http://127.0.0.1:7104/raw` |
| Publisher | 7105 | `http://127.0.0.1:7105/info` |

```sh
curl http://127.0.0.1:7104/raw
curl http://127.0.0.1:7105/info
curl -N http://127.0.0.1:7101/stream
docker compose -f deploy/docker/compose.yml logs -f
```

Los JSON de esta carpeta se montan en lectura: permiten cambiar las listas N a N
y los puertos internos. Dentro de Docker las URLs utilizan el nombre del servicio
(`manager`, `verifier`, `storage`), no `127.0.0.1`. Reinicia los contenedores después
de cambiar su configuración. Las credenciales de demostración están definidas en
`compose.yml` y `reader.json`; sustitúyelas conjuntamente para otro despliegue.

Para cambiar solo los puertos publicados en tu máquina:

```sh
READER_PORT=8101 MANAGER_PORT=8102 VERIFIER_PORT=8103 STORAGE_PORT=8104 PUBLISHER_PORT=8105 \
  docker compose -f deploy/docker/compose.yml up -d
```

Storage conserva LevelDB en el volumen `storage-data`.

```sh
# Parar y conservar datos:
docker compose -f deploy/docker/compose.yml down
# Parar y borrar los datos de este ejemplo:
docker compose -f deploy/docker/compose.yml down --volumes
```

## Construir un servicio por separado

```sh
docker build -t phonendo-reader apps/reader
docker build -t phonendo-manager apps/manager
docker build -t phonendo-verifier apps/verifier
docker build -t phonendo-storage apps/storage
docker build -t phonendo-publisher -f apps/publisher/Dockerfile .
```

Cada contenedor admite su `config.json` montado en `/app/<servicio>/config.json`.
Manager necesita `MANAGER_PASSWORD` y sus tokens; Verifier necesita la misma clave
compartida, su token y su clave de firma (la demo monta `deploy/demo/verifier_demo_key.json`;
sin clave genera una temporal).
Storage recibe `API_TOKEN_STORAGE` y utiliza `/data/phonendo` para su base de datos.
El Reader ejecuta el ejemplo Linux configurable con `READER_CONFIG_PATH`.

## Comprobar las imágenes

```sh
./tools/test_docker.sh
```

Construye y arranca un proyecto aislado con puertos libres y volumen temporal.
Espera los cinco healthchecks, comprueba datos Verified en Storage, los SSE y la
conexión Publisher → Manager. Al terminar elimina contenedores y volúmenes.
