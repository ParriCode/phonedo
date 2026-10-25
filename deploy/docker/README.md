# Phonendo con Docker

Cada servicio operativo tiene su propio `Dockerfile` y se construye usando
únicamente su carpeta. Publisher sigue pendiente de implementación.
Los archivos `config.env`, las claves y los entornos virtuales se excluyen de las
imágenes mediante `.dockerignore`. Referencia: [contexto de construcción de Docker](https://docs.docker.com/build/concepts/context/).

## Arrancar el ejemplo completo

Desde la raíz del proyecto, con Docker y Docker Compose instalados:

```sh
docker compose -f deploy/docker/compose.yml up --build -d --wait
```

El ejemplo usa credenciales de demostración, un Reader de temperaturas simuladas
y conexiones HTTP entre los cuatro servicios. El Verifier debe tener disponible
`apps/verifier/keys.json`; Compose lo monta en lectura, sin incluirlo en la imagen.

| Servicio | Puerto local | Comprobación |
| --- | --- | --- |
| Reader | 7101 | `http://127.0.0.1:7101/health` |
| Manager | 7102 | `http://127.0.0.1:7102/` |
| Verifier | 7103 | `http://127.0.0.1:7103/` |
| Storage | 7104 | `http://127.0.0.1:7104/raw` |

```sh
curl http://127.0.0.1:7104/raw
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
READER_PORT=8101 MANAGER_PORT=8102 VERIFIER_PORT=8103 STORAGE_PORT=8104 \
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
```

Cada contenedor admite su `config.json` montado en `/app/<servicio>/config.json`.
Manager necesita `MANAGER_PASSWORD` y sus tokens; Verifier necesita la misma clave
compartida, su token y `keys.json` montado en `/app/verifier/keys.json`.
Storage recibe `API_TOKEN_STORAGE` y utiliza `/data/phonendo` para su base de datos.
El Reader ejecuta el ejemplo Linux configurable con `READER_CONFIG_PATH`.

## Comprobar las imágenes

```sh
./tools/test_docker.sh
```

Construye y arranca un proyecto aislado con puertos libres y volumen temporal.
Espera los healthchecks, comprueba datos Verified en Storage y lee SSE del Reader
y Verifier. Al terminar elimina sus contenedores y volumen, también ante errores.
