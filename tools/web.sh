#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

install_packages() {
    local elevate=()
    if [[ "$EUID" -ne 0 ]]; then
        if ! command -v sudo >/dev/null 2>&1; then
            echo 'Se necesita sudo para instalar las dependencias del sistema.' >&2
            exit 1
        fi
        elevate=(sudo)
    fi
    if command -v apt-get >/dev/null 2>&1; then
        "${elevate[@]}" apt-get update
        "${elevate[@]}" apt-get install -y python3 xdg-utils
    else
        echo 'Instalación automática de paquetes disponible en Linux con apt-get.' >&2
        echo 'Instala Python 3 y vuelve a ejecutar el script.' >&2
        exit 1
    fi
}

if ! command -v python3 >/dev/null 2>&1; then
    install_packages
fi
if [[ "$(uname -s)" == Linux ]] && ! command -v xdg-open >/dev/null 2>&1; then
    install_packages
fi

# Usa la configuración local del Publisher; PUBLISHER_CONFIG_PATH permite elegir otra.
publisher_config="${PUBLISHER_CONFIG_PATH:-$ROOT_DIR/apps/publisher/config.json}"
exec python3 - "$ROOT_DIR/apps/web" "${WEB_PORT:-8080}" "$publisher_config" <<'PY'
import functools
import json
import re
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class WebHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        # El mismo puerto antes servía Leptos: ignora su HTML cacheado.
        for header in ('If-Modified-Since', 'If-None-Match'):
            if header in self.headers:
                del self.headers[header]
        return super().send_head()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


handler = functools.partial(WebHandler, directory=sys.argv[1])
config = json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))
contracts = sorted({value for value in config.get('contracts', {}).values()
                    if isinstance(value, str) and re.fullmatch(r'C[A-Z2-7]{55}', value)})
stellar_url = 'https://stellar.expert/explorer/testnet'
if contracts:
    stellar_url += '/contract/' + contracts[0]


def open_tabs(local_url):
    # La petición solo termina cuando serve_forever ya está atendiendo.
    try:
        with urllib.request.urlopen(local_url, timeout=10) as response:
            response.read()
    except OSError as error:
        print(f'No se pudo comprobar la web: {error}', file=sys.stderr, flush=True)
        return
    opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
    for url in (local_url, stellar_url):
        try:
            result = subprocess.run([opener, url], timeout=15, capture_output=True, text=True)
            if result.returncode:
                print(f'No se pudo abrir el navegador. Abre {url}\n{result.stderr.strip()}', file=sys.stderr, flush=True)
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f'Abre {url} en tu navegador: {error}', file=sys.stderr, flush=True)


try:
    server = ThreadingHTTPServer(('127.0.0.1', int(sys.argv[2])), handler)
except OSError as error:
    sys.exit(f'No se puede arrancar la web: {error}. Para otro puerto: WEB_PORT=8081 ./tools/web.sh')
with server:
    local_url = f'http://127.0.0.1:{server.server_port}/'
    print(f'Web nueva: {local_url} · Ctrl+C para parar.', flush=True)
    print(f'Stellar testnet: {stellar_url}', flush=True)
    threading.Thread(target=open_tabs, args=(local_url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
PY
