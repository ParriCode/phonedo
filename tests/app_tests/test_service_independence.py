"""Each service must load from its own directory outside the repository."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('service,entry', [
    ('manager', 'manager.py'), ('verifier', 'verifier.py'), ('storage', 'main.py'),
])
def test_service_loads_without_repository(service, entry, tmp_path):
    isolated = tmp_path / service
    shutil.copytree(ROOT / 'apps' / service, isolated,
                    ignore=shutil.ignore_patterns('.venv', '__pycache__', '*.log', 'signing_key.json'))
    if service == 'verifier':
        # Fuera del repo no hay keys/: la clave llega por configuración, como en Docker.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        key = isolated / 'verifier-key.json'
        key.write_text(json.dumps({'d': base64.urlsafe_b64encode(Ed25519PrivateKey.generate().private_bytes_raw()).decode().rstrip('=')}))
        config = json.loads((isolated / 'config.json').read_text())
        (isolated / 'config.json').write_text(json.dumps({**config, 'keyPath': str(key)}))
    env = {**os.environ, 'MANAGER_PASSWORD': 'isolation-only',
           'MANAGER_CONFIG_PATH': str(isolated / 'config.json'),
           'VERIFIER_CONFIG_PATH': str(isolated / 'config.json'), 'PHONENDO_DB_PATH': str(tmp_path / 'db'),
           'PHONENDO_LOGGING': 'false', 'PHONENDO_VERBOSE': 'false',
           'PHONENDO_LOGS_DIR': str(tmp_path / 'logs')}
    env.pop('PYTHONPATH', None)
    code = 'import runpy, sys; sys.path.insert(0, sys.argv[1]); runpy.run_path(sys.argv[2], run_name="isolation_check")'
    result = subprocess.run([sys.executable, '-I', '-c', code, str(isolated),
                             str(isolated / entry)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
