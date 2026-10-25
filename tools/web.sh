#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"

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
        "${elevate[@]}" apt-get install -y build-essential pkg-config libssl-dev curl ca-certificates python3 xdg-utils
    else
        echo 'Instalación automática de paquetes disponible en Linux con apt-get.' >&2
        echo 'Instala compilador C, pkg-config, cabeceras OpenSSL y curl y vuelve a ejecutar el script.' >&2
        exit 1
    fi
}

if ! command -v rustup >/dev/null 2>&1; then
    if ! command -v curl >/dev/null 2>&1; then
        install_packages
    fi
    echo 'Instalando Rust...'
    installer_dir="$(mktemp -d)"
    trap 'rm -f "$installer_dir/rustup-init.sh"; rmdir "$installer_dir"' EXIT
    curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs -o "$installer_dir/rustup-init.sh"
    sh "$installer_dir/rustup-init.sh" -y --profile minimal --default-toolchain stable
    rm -f "$installer_dir/rustup-init.sh"
    rmdir "$installer_dir"
    trap - EXIT
fi

export RUSTUP_TOOLCHAIN=stable
if ! rustup run stable rustc --version >/dev/null 2>&1; then
    rustup toolchain install stable --profile minimal
fi

if [[ "$(uname -s)" == Linux ]]; then
    if ! command -v cc >/dev/null 2>&1 || ! command -v pkg-config >/dev/null 2>&1 || ! pkg-config --exists openssl; then
        echo 'Instalando dependencias de compilación...'
        install_packages
    fi
fi

if ! rustup target list --installed | grep -qx 'wasm32-unknown-unknown'; then
    echo 'Instalando el target WebAssembly...'
    rustup target add wasm32-unknown-unknown
fi

if ! command -v trunk >/dev/null 2>&1; then
    echo 'Instalando Trunk (la primera vez puede tardar varios minutos)...'
    cargo install --locked trunk --version 0.22.0
fi

if ! command -v python3 >/dev/null 2>&1; then
    install_packages
fi

# Usa la configuración local del Publisher; PUBLISHER_CONFIG_PATH permite elegir otra.
publisher_config="${PUBLISHER_CONFIG_PATH:-$ROOT_DIR/apps/publisher/config.json}"
stellar_urls="$(python3 - "$publisher_config" <<'PY'
import json
import re
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
contracts = sorted({value for value in config.get('contracts', {}).values()
                    if isinstance(value, str) and re.fullmatch(r'C[A-Z2-7]{55}', value)})
if contracts:
    for contract in contracts:
        print('https://stellar.expert/explorer/testnet/contract/' + contract)
else:
    print('https://stellar.expert/explorer/testnet')
PY
)"
while IFS= read -r url; do
    echo "Stellar testnet: $url"
    if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    elif [[ "$(uname -s)" == Darwin ]]; then
        open "$url" >/dev/null 2>&1 &
    else
        echo 'Abre ese enlace en tu navegador para ver contratos y transacciones.'
    fi
done <<< "$stellar_urls"

cd "$ROOT_DIR/apps/control/frontend"
echo 'Web: http://127.0.0.1:8080 · Ctrl+C para parar.'
echo 'El panel muestra ejemplos simulados; todavía no consume los logs reales.'
exec trunk serve "$@"
