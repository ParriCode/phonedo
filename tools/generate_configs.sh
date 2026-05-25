#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_ENV="$ROOT_DIR/deploy/env/dev.env"
ARG_VERBOSE=false
ARG_DEV=false

ROJO="\033[0;31m"
VERDE="\033[0;32m"
AMARILLO="\033[0;33m"
AZUL="\033[0;34m"
NC="\033[0m"

info()  { echo -e "${AZUL}[INFO]${NC} $1"; }
ok()    { echo -e "${VERDE}[OK]${NC} $1"; }
warn()  { echo -e "${AMARILLO}[WARN]${NC} $1"; }
error() { echo -e "${ROJO}[ERROR]${NC} $1"; }

usage() {
    cat <<EOF
Uso: $0 [opciones] [archivo_env]

Opciones:
  -v, --verbose   Activa PHONENDO_VERBOSE en los servicios
  --dev           Activa PHONENDO_DEV y PHONENDO_VERBOSE en los servicios
  --help          Muestra esta ayuda

Si no se indica archivo_env, se usa deploy/env/dev.env.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose)
            ARG_VERBOSE=true
            shift
            ;;
        --dev)
            ARG_DEV=true
            ARG_VERBOSE=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        -*)
            error "Argumento desconocido: $1"
            usage
            exit 1
            ;;
        *)
            SOURCE_ENV="$1"
            shift
            ;;
    esac
done

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

MANAGER_PASSWORD="${MANAGER_PASSWORD:-prueba123}"
PHONENDO_VERBOSE="${PHONENDO_VERBOSE:-false}"
PHONENDO_LOGGING="${PHONENDO_LOGGING:-true}"
PHONENDO_DEV="${PHONENDO_DEV:-false}"
PHONENDO_LOGS_DIR="${PHONENDO_LOGS_DIR:-$ROOT_DIR/logs/services}"

if [[ "$ARG_VERBOSE" == true ]]; then
    PHONENDO_VERBOSE=true
fi

if [[ "$ARG_DEV" == true ]]; then
    PHONENDO_DEV=true
    PHONENDO_VERBOSE=true
fi

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
API_TOKEN_STORAGE=${API_TOKEN_STORAGE}
PHONENDO_VERBOSE=${PHONENDO_VERBOSE}
PHONENDO_LOGGING=${PHONENDO_LOGGING}
PHONENDO_DEV=${PHONENDO_DEV}
PHONENDO_LOGS_DIR=${PHONENDO_LOGS_DIR}"

write_file "$ROOT_DIR/apps/verifier/config.env" "PORT_VERIFIER=${PORT_VERIFIER}
API_TOKEN_VERIFIER=${API_TOKEN_VERIFIER}
PHONENDO_VERBOSE=${PHONENDO_VERBOSE}
PHONENDO_LOGGING=${PHONENDO_LOGGING}
PHONENDO_DEV=${PHONENDO_DEV}
PHONENDO_LOGS_DIR=${PHONENDO_LOGS_DIR}"

write_file "$ROOT_DIR/apps/manager/config.env" "PORT_MANAGER=${PORT_MANAGER}
API_TOKEN_MANAGER=${API_TOKEN_MANAGER}
API_TOKEN_STORAGE=${API_TOKEN_STORAGE}
API_TOKEN_VERIFIER=${API_TOKEN_VERIFIER}
API_TOKEN_PUBLISHER=${API_TOKEN_PUBLISHER}
MANAGER_PASSWORD=${MANAGER_PASSWORD}
INTERNAL_URL_STORAGE_DEVICES=${INTERNAL_URL_STORAGE_DEVICES}
INTERNAL_URL_STORAGE_EVENTS=${INTERNAL_URL_STORAGE_EVENTS}
INTERNAL_URL_VERIFIER_VERIFY=${INTERNAL_URL_VERIFIER_VERIFY}
INTERNAL_URL_STORAGE_REGISTER_DEVICES=${INTERNAL_URL_STORAGE_REGISTER_DEVICES}
INTERNAL_URL_PUBLISHER_PUBLISH=${INTERNAL_URL_PUBLISHER_PUBLISH}
PHONENDO_VERBOSE=${PHONENDO_VERBOSE}
PHONENDO_LOGGING=${PHONENDO_LOGGING}
PHONENDO_DEV=${PHONENDO_DEV}
PHONENDO_LOGS_DIR=${PHONENDO_LOGS_DIR}"


write_file "$ROOT_DIR/apps/reader/config.env" "PORT_READER=${PORT_READER}
API_TOKEN_MANAGER=${API_TOKEN_MANAGER}
INTERNAL_URL_MANAGER_REGISTER_DEVICE=${INTERNAL_URL_MANAGER_REGISTER_DEVICE}
INTERNAL_URL_MANAGER_NEW_EVENT=${INTERNAL_URL_MANAGER_NEW_EVENT}
PHONENDO_VERBOSE=${PHONENDO_VERBOSE}
PHONENDO_LOGGING=${PHONENDO_LOGGING}
PHONENDO_DEV=${PHONENDO_DEV}
PHONENDO_LOGS_DIR=${PHONENDO_LOGS_DIR}"

write_file "$ROOT_DIR/apps/publisher/config.env" "PORT_PUBLISHER=${PORT_PUBLISHER}
API_TOKEN_PUBLISHER=${API_TOKEN_PUBLISHER}
PHONENDO_VERBOSE=${PHONENDO_VERBOSE}
PHONENDO_LOGGING=${PHONENDO_LOGGING}
PHONENDO_DEV=${PHONENDO_DEV}
PHONENDO_LOGS_DIR=${PHONENDO_LOGS_DIR}"

ok "Todos los config.env han sido generados"
