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

: "${MANAGER_PASSWORD:?MANAGER_PASSWORD is required}"
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
MANAGER_PASSWORD=${MANAGER_PASSWORD}
PHONENDO_VERBOSE=${PHONENDO_VERBOSE}
PHONENDO_LOGGING=${PHONENDO_LOGGING}
PHONENDO_DEV=${PHONENDO_DEV}
PHONENDO_LOGS_DIR=${PHONENDO_LOGS_DIR}"

write_file "$ROOT_DIR/apps/manager/config.env" "PORT_MANAGER=${PORT_MANAGER}
MANAGER_HTTP_TIMEOUT_SECONDS=${MANAGER_HTTP_TIMEOUT_SECONDS:-10}
MANAGER_QUEUE_SIZE=${MANAGER_QUEUE_SIZE:-1000}
MANAGER_RETRY_INTERVAL_SECONDS=${MANAGER_RETRY_INTERVAL_SECONDS:-5}
API_TOKEN_MANAGER=${API_TOKEN_MANAGER}
API_TOKEN_STORAGE=${API_TOKEN_STORAGE}
API_TOKEN_VERIFIER=${API_TOKEN_VERIFIER}
API_TOKEN_PUBLISHER=${API_TOKEN_PUBLISHER}
MANAGER_PASSWORD=${MANAGER_PASSWORD}
PHONENDO_VERBOSE=${PHONENDO_VERBOSE}
PHONENDO_LOGGING=${PHONENDO_LOGGING}
PHONENDO_DEV=${PHONENDO_DEV}
PHONENDO_LOGS_DIR=${PHONENDO_LOGS_DIR}"


write_file "$ROOT_DIR/apps/reader/config.env" "PORT_READER=${PORT_READER}
API_TOKEN_MANAGER=${API_TOKEN_MANAGER}
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

# Clave ed25519 del Verifier (firma eventos y lotes): la de desarrollo de circuits/ si existe,
# porque es la que conoce el contrato desplegado; si no, una nueva
KEY_FILE="$ROOT_DIR/apps/verifier/signing_key.json"
DEV_KEY="$ROOT_DIR/circuits/build/verifier_dev_key.json"
if [[ ! -f "$KEY_FILE" && -f "$DEV_KEY" ]]; then
    cp "$DEV_KEY" "$KEY_FILE"
    ok "Copiado $DEV_KEY a $KEY_FILE"
elif [[ ! -f "$KEY_FILE" ]]; then
    "${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}" - "$KEY_FILE" <<'EOF'
import base64, json, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

key = Ed25519PrivateKey.generate()
encode = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip("=")
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({"kty": "OKP", "crv": "Ed25519", "d": encode(key.private_bytes_raw()),
               "x": encode(key.public_key().public_bytes_raw())}, f)
EOF
    warn "Generado $KEY_FILE: el contrato debe desplegarse con su clave pública"
fi
