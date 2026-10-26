#!/usr/bin/env bash
# Claves de Verifiers y carteras de Publishers en keys/. Ayuda: ./tools/keys.sh --help
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
exec "$PYTHON_BIN" "$ROOT_DIR/tools/keys.py" "$@"
