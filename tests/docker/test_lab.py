"""Real Docker backend used by the desktop interface, including resume."""
import importlib.util
from pathlib import Path
import queue
import socket
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('lab_docker', ROOT / 'tools/lab_docker.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def wait_for(check, seconds=20):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            value = check()
            if value:
                return value
        except requests.RequestException:
            pass
        time.sleep(.15)
    raise AssertionError('Servicio o resultado no disponible')


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def test_docker_lab_manual_periodic_and_resume():
    events = queue.Queue()
    session = lab.DockerSession(events)
    instances = {}
    def start(kind, config):
        instance = lab.DockerInstance(session, kind, kind+'-1', port(), config)
        instances[kind] = instance
        wait_for(lambda: requests.get(instance.url + ('/health' if kind=='reader' else '/'), timeout=1).status_code == 200)
        return instance
    try:
        storage = start('storage', {'services': {'managers': []}})
        verifier = start('verifier', {'services': {'managers': []}})
        manager = start('manager', {'services': {'storages': [storage.docker_url], 'verifiers': [verifier.docker_url]}})
        reader = start('reader', {'readerId': 'reader-lab-test', 'server': {'enabled': True},
            'services': {'managers': [{'url': manager.docker_url, 'token': session.credentials['API_TOKEN_MANAGER']}]}})
        reader.command({'action': 'add', 'device': 'device-tool', 'sensor': 'sensor-tool', 'property': 'temperature', 'unit': 'CELSIUS'})
        reader.command({'action': 'emit', 'device': 'device-tool', 'sensor': 'sensor-tool', 'value': 23.5})
        def values():
            records = requests.get(storage.url+'/raw', timeout=2).json()
            return [v['payload']['simple_result'] for v in records.values() if v.get('status') == 'Verified']
        assert 23.5 in values()
        reader.command({'action': 'periodic', 'device': 'device-tool', 'sensor': 'sensor-tool', 'values': [31,32], 'interval': .2})
        wait_for(lambda: 31 in values() and 32 in values())
        reader.pause()
        assert reader.state() == 'paused'
        count = len(values())
        time.sleep(.5)
        assert len(values()) == count
        reader.resume()
        wait_for(lambda: len(values()) > count)
        reader.stop()
        assert reader.state() == 'exited'
        count = len(values())
        reader.resume()
        wait_for(lambda: requests.get(reader.url+'/health', timeout=1).status_code == 200)
        assert reader.command({'action': 'list'})['devices'] == [{'device': 'device-tool', 'sensors': ['sensor-tool']}]
        wait_for(lambda: len(values()) > count)
        reader.command({'action': 'stop', 'device': 'device-tool', 'sensor': 'sensor-tool'})
        time.sleep(.3)
        saved = requests.get(storage.url+'/raw', timeout=2).json()
        storage.stop()
        assert storage.state() == 'exited'
        storage.resume()
        wait_for(lambda: requests.get(storage.url+'/', timeout=1).status_code == 200)
        assert requests.get(storage.url+'/raw', timeout=2).json() == saved
        reader.command({'action': 'emit', 'device': 'device-tool', 'sensor': 'sensor-tool', 'value': 99})
        wait_for(lambda: 99 in values())
    except Exception:
        for instance in session.instances:
            print(session.run('logs', '--tail', '30', instance.container))
        raise
    finally:
        session.close()
    assert all(not instance.exists() for instance in instances.values())


def test_remove_all_only_removes_its_session():
    import uuid
    session = lab.DockerSession(queue.Queue())
    owned = []
    sentinel = 'phonendo-delete-sentinel-' + uuid.uuid4().hex[:8]
    try:
        for name in ['reader-a','reader-b']:
            instance = lab.DockerInstance(session,'reader',name,port(),
                {'readerId':name,'server':{'enabled':True},'services':{'managers':[]}})
            owned.append(instance)
        session.run('run','-d','--name',sentinel,'--entrypoint','python','phonendo-lab-reader',
                    '-c','import time; time.sleep(90)')
        owned[0].pause()
        result = session.remove_all()
        assert set(result['removed']) == {'reader-a','reader-b'}
        assert result['errors'] == []
        assert session.instances == []
        assert all(not instance.exists() for instance in owned)
        assert all(not Path(instance.directory.name).exists() for instance in owned)
        assert session.run('inspect','--format','{{.State.Running}}',sentinel) == 'true'
        assert session.remove_all() == {'removed':[], 'errors':[]}
    finally:
        session.run('rm','-f',sentinel) if session.run('ps','-aq','--filter','name=^'+sentinel+'$') else None
        session.close()
