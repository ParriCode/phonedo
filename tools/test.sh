#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [[ $# -gt 0 ]]; then
    pattern="$1"
else
    pattern='test_*.py'
fi
export PYTHONPATH="$ROOT_DIR/apps/manager:$ROOT_DIR/apps/reader/python/core:$ROOT_DIR/apps/reader/python/server${PYTHONPATH:+:$PYTHONPATH}"
for script in tools/*.sh; do
    bash -n "$script"
done
mapfile -t test_files < <(find tests/app_tests -maxdepth 1 -name "$pattern" -type f | sort)
if [[ ${#test_files[@]} -eq 0 ]]; then
    echo "No hay pruebas para $pattern" >&2
    exit 1
fi
exec "$PYTHON_BIN" -m pytest "${test_files[@]}" -v
