#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PROJECT="phonendo-test-${RANDOM}-${RANDOM}"
read -r READER_PORT MANAGER_PORT VERIFIER_PORT STORAGE_PORT PUBLISHER_PORT < <(python3 - <<'PY'
import socket
sockets = [socket.socket() for _ in range(5)]
for sock in sockets:
    sock.bind(('127.0.0.1', 0))
print(*(sock.getsockname()[1] for sock in sockets))
for sock in sockets:
    sock.close()
PY
)
export READER_PORT MANAGER_PORT VERIFIER_PORT STORAGE_PORT PUBLISHER_PORT
COMPOSE=(docker compose -p "$PROJECT" -f deploy/docker/compose.yml)
cleanup() {
    result=$?
    if [[ "$result" -ne 0 ]]; then
        "${COMPOSE[@]}" logs --tail=80 >&2 || true
    fi
    "${COMPOSE[@]}" down --volumes --remove-orphans > /dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"${COMPOSE[@]}" up --build -d --wait --wait-timeout 90
python3 - <<'PY'
import json
import os
import time
import urllib.request

base = {name: 'http://127.0.0.1:' + os.environ[name.upper() + '_PORT']
        for name in ('reader', 'manager', 'verifier', 'storage', 'publisher')}
def get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)

# The real Reader produces observations and automatically registers its device.
end = time.monotonic() + 20
while True:
    records = get(base['storage'] + '/raw')
    verified = [v for v in records.values() if v.get('status') == 'Verified']
    if verified:
        assert verified[0]['readerId'] == 'reader-docker'
        assert verified[0]['verifierSign'] and verified[0]['managerHash']
        break
    assert time.monotonic() < end, 'No Verified events reached Storage'
    time.sleep(.2)

# Verify SSE is reachable through the published Docker ports.
with urllib.request.urlopen(base['reader'] + '/stream', timeout=10) as response:
    while True:
        line = response.readline()
        if line.startswith(b'data: '):
            assert json.loads(line[6:])['readerId'] == 'reader-docker'
            break
request = urllib.request.Request(base['verifier'] + '/stream',
                                  headers={'Authorization': 'Bearer demo-verifier'})
with urllib.request.urlopen(request, timeout=10) as response:
    while True:
        line = response.readline()
        if line.startswith(b'data: '):
            assert json.loads(line[6:])['value']['status'] == 'Verified'
            break

# Publisher is alive and subscribed to the Manager stream.
end = time.monotonic() + 10
while True:
    if {'peer': 'http://manager:3003', 'transport': 'sse'} in get(base['publisher'] + '/info'):
        break
    assert time.monotonic() < end, 'Publisher did not connect to Manager SSE'
    time.sleep(.2)
print('OK: cinco contenedores saludables; flujo base y Publisher conectado al Manager por SSE.')
PY
