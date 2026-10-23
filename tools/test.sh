#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ $# -gt 0 ]]; then
    pattern="$1"
else
    pattern='test_*.py'
fi
export PYTHONPATH="$ROOT_DIR/apps/manager:$ROOT_DIR/libs:$ROOT_DIR/apps/reader/python/core:$ROOT_DIR/apps/reader/python/server${PYTHONPATH:+:$PYTHONPATH}"
for script in tools/*.sh; do
    bash -n "$script"
done
exec "$PYTHON_BIN" -m unittest discover -s tests/app_tests -p "$pattern" -v
