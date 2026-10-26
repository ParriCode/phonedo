#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGENERATE_KEYS=false
REBUILD=false

usage() {
    cat <<EOF
Uso: $0 [opciones]

Sirve la consola del operador en http://127.0.0.1:${WEB_PORT:-8080}/operator.html.
Antes deja listas las claves de keys/ (crea solo las que falten).

Opciones:
  --regenerate-keys  Sustituye las carteras de keys/stellar por otras nuevas y fondeadas
                     (guarda copia de las anteriores). Por defecto no.
  --rebuild          Reconstruye y relanza la pila Docker de Phonendo
                     (deploy/docker/compose.yml). Por defecto no.
  --help             Muestra esta ayuda
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --regenerate-keys) REGENERATE_KEYS=true ;;
        --rebuild) REBUILD=true ;;
        --help) usage; exit 0 ;;
        *) echo "Argumento desconocido: $1" >&2; usage >&2; exit 1 ;;
    esac
    shift
done

install_packages() {
    local elevate=()
    if [[ "$EUID" -ne 0 ]]; then elevate=(sudo); fi
    if command -v apt-get >/dev/null 2>&1; then
        "${elevate[@]}" apt-get update
        "${elevate[@]}" apt-get install -y python3 python3-venv xdg-utils
    else
        echo 'Instala Python 3 con venv y un navegador para ejecutar el panel.' >&2
        exit 1
    fi
}
if ! command -v python3 >/dev/null 2>&1; then install_packages; fi
if [[ "$(uname -s)" == Linux ]] && ! command -v xdg-open >/dev/null 2>&1; then install_packages; fi

WEB_PYTHON="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$WEB_PYTHON" ]]; then
    if ! python3 -m venv "$ROOT_DIR/.venv"; then
        install_packages
        python3 -m venv "$ROOT_DIR/.venv"
    fi
fi
if ! "$WEB_PYTHON" -c 'import aiohttp, cryptography' >/dev/null 2>&1; then
    "$WEB_PYTHON" -m pip install 'aiohttp>=3.9,<4' cryptography
fi
# Claves de Verifier y carteras en keys/: un tercero solo tiene que poner aquí las suyas.
if [[ "$REGENERATE_KEYS" == true ]]; then
    "$WEB_PYTHON" "$ROOT_DIR/tools/keys.py" init --regenerate-wallets
else
    "$WEB_PYTHON" "$ROOT_DIR/tools/keys.py" init
fi
if [[ "$REBUILD" == true ]]; then
    docker compose -f "$ROOT_DIR/deploy/docker/compose.yml" up --build -d --wait
fi
# La web es React + Vite: se compila en apps/web/dist antes de servirla.
if command -v npm >/dev/null 2>&1; then
    (cd "$ROOT_DIR/apps/web" && { [[ -d node_modules ]] || npm ci; } && npm run build)
elif [[ ! -f "$ROOT_DIR/apps/web/dist/operator.html" ]]; then
    echo 'Instala Node.js 20 o superior para compilar la web (apps/web).' >&2
    exit 1
fi
echo "Panel: http://127.0.0.1:${WEB_PORT:-8080}/operator.html · Ctrl+C para parar."
echo 'Los servicios se despliegan en Docker y siguen ejecutándose al cerrar la web.'
if ! command -v docker >/dev/null 2>&1; then
    echo 'Aviso: necesitas Docker Engine o Docker Desktop para desplegar servicios.' >&2
fi
exec "$WEB_PYTHON" "$ROOT_DIR/tools/web_runtime.py"
