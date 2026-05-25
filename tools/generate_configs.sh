#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_ENV="${1:-$ROOT_DIR/deploy/env/dev.env}"

ROJO="\033[0;31m"
VERDE="\033[0;32m"
AMARILLO="\033[0;33m"
AZUL="\033[0;34m"
NC="\033[0m"

info()  { echo -e "${AZUL}[INFO]${NC} $1"; }
ok()    { echo -e "${VERDE}[OK]${NC} $1"; }
warn()  { echo -e "${AMARILLO}[WARN]${NC} $1"; }
error() { echo -e "${ROJO}[ERROR]${NC} $1"; }

if [[ ! -f "$SOURCE_ENV" ]]; then
    error "No existe el archivo de configuración maestro: $SOURCE_ENV"
    exit 1
fi

# Cargar variables del archivo maestro
set -a
# shellcheck disable=SC1090
source "$SOURCE_ENV"
set +a

# Validación mínima
required_vars=(
    HOST
    PORT_STORAGE
    PORT_VERIFIER
    PORT_MANAGER
    PORT_READER
    PORT_PUBLISHER
    API_TOKEN_STORAGE
    API_TOKEN_VERIFIER
    API_TOKEN_MANAGER
    API_TOKEN_PUBLISHER
)

for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        error "Falta la variable obligatoria: $var"
        exit 1
    fi
done

# URLs derivadas
INTERNAL_URL_STORAGE_DEVICES="http://${HOST}:${PORT_STORAGE}/devices"
INTERNAL_URL_STORAGE_EVENTS="http://${HOST}:${PORT_STORAGE}/events"
INTERNAL_URL_VERIFIER_VERIFY="http://${HOST}:${PORT_VERIFIER}/verify"
INTERNAL_URL_MANAGER_REGISTER_DEVICE="http://${HOST}:${PORT_MANAGER}/registerDevice"
INTERNAL_URL_MANAGER_NEW_EVENT="http://${HOST}:${PORT_MANAGER}/newEvent"
INTERNAL_URL_PUBLISHER_PUBLISH="http://${HOST}:${PORT_PUBLISHER}/publish"
INTERNAL_URL_STORAGE_REGISTER_DEVICES="http://${HOST}:${PORT_STORAGE}/registerDevice"

write_file() {
    local target="$1"
    shift

    mkdir -p "$(dirname "$target")"
    cat > "$target" <<EOF
$*
EOF
    ok "Generado $target"
}

info "Generando config.env de los servicios..."

write_file "$ROOT_DIR/apps/storage/config.env" "PORT_STORAGE=${PORT_STORAGE}
API_TOKEN_STORAGE=${API_TOKEN_STORAGE}"

write_file "$ROOT_DIR/apps/verifier/config.env" "PORT_VERIFIER=${PORT_VERIFIER}
API_TOKEN_VERIFIER=${API_TOKEN_VERIFIER}"

write_file "$ROOT_DIR/apps/manager/config.env" "PORT_MANAGER=${PORT_MANAGER}
API_TOKEN_MANAGER=${API_TOKEN_MANAGER}
API_TOKEN_STORAGE=${API_TOKEN_STORAGE}
API_TOKEN_VERIFIER=${API_TOKEN_VERIFIER}
API_TOKEN_PUBLISHER=${API_TOKEN_PUBLISHER}
MANAGER_PASSWORD=prueba123
INTERNAL_URL_STORAGE_DEVICES=${INTERNAL_URL_STORAGE_DEVICES}
INTERNAL_URL_STORAGE_EVENTS=${INTERNAL_URL_STORAGE_EVENTS}
INTERNAL_URL_VERIFIER_VERIFY=${INTERNAL_URL_VERIFIER_VERIFY}
INTERNAL_URL_STORAGE_REGISTER_DEVICES=${INTERNAL_URL_STORAGE_REGISTER_DEVICES}
INTERNAL_URL_PUBLISHER_PUBLISH=${INTERNAL_URL_PUBLISHER_PUBLISH}"


write_file "$ROOT_DIR/apps/reader/config.env" "PORT_READER=${PORT_READER}
API_TOKEN_MANAGER=${API_TOKEN_MANAGER}
INTERNAL_URL_MANAGER_REGISTER_DEVICE=${INTERNAL_URL_MANAGER_REGISTER_DEVICE}
INTERNAL_URL_MANAGER_NEW_EVENT=${INTERNAL_URL_MANAGER_NEW_EVENT}"

write_file "$ROOT_DIR/apps/publisher/config.env" "PORT_PUBLISHER=${PORT_PUBLISHER}
API_TOKEN_PUBLISHER=${API_TOKEN_PUBLISHER}"

ok "Todos los config.env han sido generados"