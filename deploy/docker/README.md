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

## Cobro real en testnet

Prepara antes `circuits/` con `npm run setup`. El Publisher firma con una cuenta de
Stellar cuya clave secreta recibe por entorno y que nunca entra en la imagen. Crea
`deploy/docker/.env` (ignorado por git) con la clave de tu alias:

```sh
echo "STELLAR_SECRET_KEY=$(stellar keys show alex)" > deploy/docker/.env
```

En PowerShell: `"STELLAR_SECRET_KEY=$(stellar keys show alex)" | Set-Content -Encoding ascii deploy/docker/.env`.

El contenedor crea con ella el alias `alex`. `deploy/docker/publisher.json` indica a qué
contrato va cada caso: `contracts` por `verifierId` (rehabilitación) y `devices` por
dispositivo (cadena de frío). Sin `.env` el Publisher prepara los lotes pero no cobra.
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
compartida, su token y `signing_key.json` montado en `/app/verifier/signing_key.json`.
Storage recibe `API_TOKEN_STORAGE` y utiliza `/data/phonendo` para su base de datos.
El Reader ejecuta el ejemplo Linux configurable con `READER_CONFIG_PATH`.

## Comprobar las imágenes

```sh
./tools/test_docker.sh
```

Construye y arranca un proyecto aislado con puertos libres y volumen temporal.
Espera los cinco healthchecks, comprueba datos Verified en Storage, los SSE y la
conexión Publisher → Manager. Al terminar elimina contenedores y volúmenes.
