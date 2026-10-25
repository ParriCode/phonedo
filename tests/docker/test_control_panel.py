"""Backend del panel contra la pila Docker real: Reader, Manager, Verifier, Storage y Publisher."""
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ('reader', 'manager', 'verifier', 'storage', 'publisher')
ADMIN, PATIENT, INSURER = (secrets.token_hex(16) for _ in range(3))
# Tokens de demo del Compose: nunca deben aparecer en lo que sirve el panel.
COMPOSE_SECRETS = ('demo-manager', 'demo-storage', 'demo-verifier', 'demo-shared-secret')

pytestmark = pytest.mark.skipif(shutil.which('docker') is None, reason='requiere Docker')


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_for(check, seconds=60, message='Servicio o resultado no disponible'):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            value = check()
            if value:
                return value
        except requests.RequestException:
            pass
        time.sleep(.5)
    raise AssertionError(message)


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', **kwargs)


def seed(project):
    """Semilla del inventario con los nombres de contenedor de este proyecto."""
    data = json.loads((ROOT / 'apps/control/backend/seed.json').read_text(encoding='utf-8'))
    for instance in data['deployments'][0]['instances']:
        instance['container'] = instance['container'].replace('phonendo-', f'{project}-', 1)
    return data


class Panel:
    def __init__(self, url, project):
        self.url, self.project = url, project

    def get(self, path, token=ADMIN, **kwargs):
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        return requests.get(self.url + path, headers=headers, timeout=10, **kwargs)

    def action(self, instance, action, token=ADMIN):
        return requests.post(f'{self.url}/api/instances/{instance}/actions', json={'action': action},
                             headers={'Authorization': f'Bearer {token}'}, timeout=10)

    def topology(self):
        return self.get('/api/deployments/docker-local/topology').json()

    def node(self, instance):
        return next(n for n in self.topology()['nodes'] if n['instanceId'] == instance)

    def finished(self, operation_id, seconds=60):
        def check():
            operation = self.get(f'/api/operations/{operation_id}').json()
            return operation if operation['status'] in ('succeeded', 'failed') else None
        return wait_for(check, seconds, f'La operación {operation_id} no terminó')


@pytest.fixture(scope='module')
def panel(tmp_path_factory):
    project = f'phonendo-control-{secrets.token_hex(3)}'
    env = dict(os.environ, **{f'{name.upper()}_PORT': str(port()) for name in SERVICES})
    compose = ['docker', 'compose', '-p', project, '-f', str(ROOT / 'deploy/docker/compose.yml'),
               '-f', str(ROOT / 'tests/docker/control_labels.yml')]
    control = f'{project}-control'
    data_volume = f'{project}-control-data'
    seed_dir = tmp_path_factory.mktemp('control')
    (seed_dir / 'seed.json').write_text(json.dumps(seed(project)), encoding='utf-8')
    panel_port = port()
    try:
        run(*compose, 'up', '--build', '-d', '--wait', '--wait-timeout', '180', env=env)
        run('docker', 'build', '-q', '-t', 'phonendo-control:test', str(ROOT / 'apps/control/backend'))
        run('docker', 'run', '-d', '--name', control, '--network', f'{project}_default',
            '-p', f'127.0.0.1:{panel_port}:7200',
            '-v', '/var/run/docker.sock:/var/run/docker.sock',
            '-v', f'{seed_dir}:/seed:ro', '-v', f'{data_volume}:/data',
            '-e', 'CONTROL_SEED=/seed/seed.json', '-e', 'CONTROL_POLL_MS=1000',
            '-e', f'CONTROL_ADMIN_TOKEN={ADMIN}', '-e', f'CONTROL_PATIENT_TOKEN={PATIENT}',
            '-e', f'CONTROL_INSURER_TOKEN={INSURER}',
            'phonendo-control:test')
        instance = Panel(f'http://127.0.0.1:{panel_port}', project)
        instance.env, instance.control = env, control
        wait_for(lambda: instance.get('/api/health', token=None).ok, 30, 'El panel no arrancó')
        yield instance
    except subprocess.CalledProcessError as error:
        pytest.fail(f'{" ".join(error.cmd[:4])}...: {error.stderr[-2000:]}')
    finally:
        logs = subprocess.run(['docker', 'logs', '--tail', '40', control], capture_output=True, text=True,
                              encoding='utf-8', errors='replace')
        print(logs.stdout, logs.stderr)
        subprocess.run(['docker', 'rm', '-f', control], capture_output=True)
        subprocess.run(['docker', 'volume', 'rm', data_volume], capture_output=True)
        subprocess.run([*compose, 'down', '--volumes', '--remove-orphans'], capture_output=True, env=env)


def test_all_services_are_healthy_and_connected(panel):
    def all_healthy():
        topology = panel.topology()
        nodes = {n['instanceId']: n for n in topology['nodes']}
        ok = len(nodes) == 5 and all(n['status'] == 'healthy' and not n['stale'] for n in nodes.values())
        return topology if ok else None
    topology = wait_for(all_healthy, 60, 'No todos los servicios aparecen healthy')

    assert not topology['simulated']
    assert all(n['containerState'] == 'running' for n in topology['nodes'])
    states = {(c['sourceId'], c['targetId'], c['transport']): c['state']
              for c in topology['connections'] if c['desired']}
    assert states == {
        ('local-reader', 'local-manager', 'http'): 'configured',
        ('local-manager', 'local-verifier', 'http'): 'configured',
        ('local-manager', 'local-storage', 'http'): 'configured',
        ('local-manager', 'local-publisher', 'sse'): 'connected',
    }


def test_instance_detail_matches_docker_and_reader(panel):
    detail = panel.get('/api/instances/local-reader', token=PATIENT).json()
    assert detail['readerId'] == 'reader-docker'
    assert detail['docker']['state'] == 'running'
    assert detail['docker']['name'] == f'{panel.project}-reader-1'
    published = {p['publicPort'] for p in detail['docker']['ports']}
    assert int(panel.env['READER_PORT']) in published
    assert detail['devices'], 'El Reader no informa de dispositivos'
    assert {'peer': 'http://manager:3003', 'transport': 'http'} in detail['peers']


def test_verified_readings_reach_the_panel(panel):
    readings = wait_for(lambda: panel.get('/api/readings?deployment=docker-local&limit=5', token=PATIENT)
                        .json()['items'], 60, 'No llegan lecturas verificadas')
    assert len(readings) <= 5
    first = readings[0]
    assert first['kind'] == 'verified'
    assert first['readerId'] == 'reader-docker'
    dates = [r['createdAt'] for r in readings]
    assert dates == sorted(dates, reverse=True)

    device = first['deviceId']
    filtered = panel.get(f'/api/readings?deployment=docker-local&deviceId={device}').json()['items']
    assert filtered and all(r['deviceId'] == device for r in filtered)
    assert panel.get('/api/readings?deployment=docker-local&deviceId=no-existe').json()['items'] == []


def test_insurer_never_receives_private_data(panel):
    for path in ('/api/readings?deployment=docker-local', '/api/instances/local-reader/logs',
                 '/api/instances/local-reader'):
        response = panel.get(path, token=INSURER)
        assert response.status_code == 403, path
        assert response.json()['code'] == 'role_forbidden'
        assert panel.get(path, token=None).status_code == 401, path
        assert panel.get(path, token='inventado').status_code == 401, path

    me = panel.get('/api/me', token=INSURER).json()
    assert me == {'role': 'insurer', 'authRequired': True, 'canReadPrivate': False, 'canAct': False}
    sessions = panel.get('/api/sessions', token=INSURER)
    assert sessions.status_code == 200
    assert sessions.json()['lastError']['code'] == 'stellar_disabled'
    # El mapa no lleva datos privados.
    assert panel.get('/api/deployments/docker-local/topology', token=None).status_code == 200


def test_responses_do_not_expose_service_secrets(panel):
    texts = [panel.get(path).text for path in (
        '/api/deployments/docker-local/topology',
        '/api/instances/local-manager', '/api/instances/local-verifier',
        '/api/instances/local-manager/logs?limit=200', '/api/instances/local-storage/logs?limit=200',
        '/api/readings?deployment=docker-local&limit=50',
    )]
    lines = panel.get('/api/instances/local-manager/logs?limit=200').json()['lines']
    assert lines, 'El Manager no devuelve logs'
    for text in texts:
        for secret in COMPOSE_SECRETS + (ADMIN, PATIENT, INSURER):
            assert secret not in text


def test_stream_sends_snapshot_then_live_updates(panel):
    with requests.get(panel.url + '/api/stream?deployment=docker-local', stream=True, timeout=15) as response:
        assert response.headers['content-type'].startswith('text/event-stream')
        events = []
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('event: '):
                events.append(line[7:])
            if len(events) == 2:
                break
    assert events == ['snapshot', 'topology']


def test_unlabelled_or_unauthorised_actions_are_refused(panel):
    response = panel.action('local-publisher', 'restart')
    assert response.status_code == 403
    assert response.json()['code'] == 'container_not_managed'
    assert panel.action('local-verifier', 'stop', token=PATIENT).status_code == 403
    assert panel.action('local-verifier', 'stop', token=INSURER).status_code == 403
    assert panel.node('local-publisher')['containerState'] == 'running'


def test_stopping_and_starting_verifier_recovers_the_pipeline(panel):
    response = panel.action('local-verifier', 'stop')
    assert response.status_code == 202
    assert panel.finished(response.json()['operationId'])['status'] == 'succeeded'

    def verifier_down():
        topology = panel.topology()
        node = next(n for n in topology['nodes'] if n['instanceId'] == 'local-verifier')
        link = next(c for c in topology['connections'] if c['targetId'] == 'local-verifier')
        return node['status'] == 'offline' and node['containerState'] == 'exited' and link['state'] == 'disconnected'
    wait_for(verifier_down, 30, 'El panel no refleja el Verifier parado')

    restarted_at = time.time()
    response = panel.action('local-verifier', 'start')
    assert panel.finished(response.json()['operationId'])['status'] == 'succeeded'
    wait_for(lambda: panel.node('local-verifier')['status'] == 'healthy', 60, 'El Verifier no vuelve a healthy')

    # El pipeline real vuelve a verificar lecturas después del arranque.
    def new_reading():
        items = panel.get('/api/readings?deployment=docker-local&limit=1').json()['items']
        created = items[0]['createdAt'] if items else None
        return created and datetime.fromisoformat(created.replace('Z', '+00:00')).timestamp() > restarted_at
    wait_for(new_reading, 60, 'No llegan lecturas verificadas tras arrancar el Verifier')


def test_operations_survive_a_panel_restart(panel):
    response = panel.action('local-reader', 'restart')
    operation_id = response.json()['operationId']
    assert panel.finished(operation_id)['status'] == 'succeeded'

    run('docker', 'restart', panel.control)
    wait_for(lambda: panel.get('/api/health', token=None).ok, 30, 'El panel no volvió a arrancar')
    history = panel.get('/api/operations?deployment=docker-local').json()
    saved = next(op for op in history if op['operationId'] == operation_id)
    assert saved['status'] == 'succeeded' and saved['action'] == 'restart'
    wait_for(lambda: panel.node('local-reader')['status'] == 'healthy', 60, 'El panel no vuelve a recoger tras reiniciarse')
