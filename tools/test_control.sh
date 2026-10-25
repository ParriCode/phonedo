#!/usr/bin/env bash
# Backend del panel contra la pila Docker real (tests/docker/test_control_panel.py).
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
exec "$PYTHON_BIN" -m pytest tests/docker/test_control_panel.py -v "$@"
