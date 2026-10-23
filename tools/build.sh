#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
exec "$PYTHON_BIN" -m compileall -q -x '/(\.venv|__pycache__)/' "$ROOT_DIR/apps" "$ROOT_DIR/libs"
