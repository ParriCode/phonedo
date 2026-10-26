"""Los destinos conservan su propio token al editar las filas del panel."""
import importlib.util
import asyncio
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location(
    'web_docker_config_test', Path(__file__).resolve().parents[2] / 'tools/web_docker.py')
docker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docker)


def test_destination_tokens_follow_url_after_removal_and_reordering():
    original = {'services': {'verifiers': [
        {'url': 'http://first:5000', 'token': 'first-token'},
        {'url': 'http://second:5000', 'token': 'second-token'}]}}
    masked = docker.redact(original)
    masked['services']['verifiers'].reverse()
    assert docker.restore(masked, original)['services']['verifiers'][0]['token'] == 'second-token'
    masked['services']['verifiers'].pop()
    assert docker.restore(masked, original)['services']['verifiers'] == [
        {'url': 'http://second:5000', 'token': 'second-token'}]


def test_new_destination_does_not_inherit_another_peers_token():
    original = [{'url': 'http://first:5000', 'token': 'first-token'}]
    updated = [{'url': 'http://new:5000', 'token': docker.MASK}]
    assert docker.restore(updated, original) == [{'url': 'http://new:5000', 'token': ''}]
    updated[0]['token'] = 'new-token'
    assert docker.restore(updated, original)[0]['token'] == 'new-token'


def test_image_actions_only_remove_images_owned_by_the_panel():
    controller = object.__new__(docker.DockerController)
    controller.lock = asyncio.Lock()
    controller.records = {}
    calls = []
    labels = {'phonendo.web.managed': 'true', 'phonendo.web.kind': 'reader'}

    async def run(*args, **_):
        calls.append(args)
        if args[:2] == ('image', 'inspect'):
            return docker.json.dumps([{'Config': {'Labels': labels}}])
        return ''

    controller.run = run
    result = asyncio.run(controller.image_action('reader', 'build'))
    assert result['built'] is True
    assert any(call[:2] == ('build', '--label') for call in calls)
    assert asyncio.run(controller.image_action('reader', 'remove'))['removed'] is True
    assert ('image', 'rm', 'phonendo-web-reader:local') in calls

    labels['phonendo.web.kind'] = 'manager'
    calls.clear()
    with pytest.raises(ValueError, match='no fue construida'):
        asyncio.run(controller.image_action('reader', 'remove'))
    assert not any(call[:2] == ('image', 'rm') for call in calls)
    with pytest.raises(ValueError, match='Tipo de servicio desconocido'):
        asyncio.run(controller.image_action('unknown', 'build'))


def test_compose_inventory_uses_real_container_labels_and_image():
    controller = object.__new__(docker.DockerController)
    info = {'Id': 'real-container-id', 'Name': '/phonendo-publisher-1',
            'Config': {'Image': 'sha256:real-image', 'Labels': {
                'com.docker.compose.project': 'phonendo', 'com.docker.compose.service': 'publisher'}},
            'NetworkSettings': {'Ports': {'3005/tcp': [{'HostPort': '7105'}]}},
            'State': {'Status': 'running'}}
    async def run(*args, **_):
        if args[0] == 'ps':
            return 'real-container-id'
        return docker.json.dumps([info])
    controller.run = run
    snapshot = asyncio.run(controller.compose_snapshot('compose-publisher'))
    assert snapshot['container'] == 'real-container-id'
    assert snapshot['image'] == 'sha256:real-image'
    assert snapshot['url'] == 'http://127.0.0.1:7105'
    info['Config']['Labels']['com.docker.compose.project'] = 'other'
    with pytest.raises(ValueError, match='no pertenece'):
        asyncio.run(controller.compose_snapshot('compose-publisher'))


def test_image_inventory_ignores_unrelated_images():
    controller = object.__new__(docker.DockerController)
    async def run(*args, **_):
        if args[:2] == ('image', 'ls'):
            return 'phonendo-reader:latest\nphonendo-web-verifier:local\nother:latest\nphonendo-random:latest'
        return 'ok'
    controller.run = run
    images = asyncio.run(controller.image_snapshots())
    assert [(item['kind'], item['imageSource']) for item in images] == [('reader', 'compose'), ('verifier', 'panel')]
    assert all(item['imageOnly'] for item in images)


def test_connection_changes_real_configs_and_restarts_both_containers(tmp_path):
    controller = object.__new__(docker.DockerController)
    controller.lock = asyncio.Lock()
    controller.directory = tmp_path
    reader = {'id': 'reader', 'kind': 'reader', 'container': 'reader-container', 'name': 'reader', 'dockerUrl': 'http://reader:3002'}
    manager = {'id': 'manager', 'kind': 'manager', 'container': 'manager-container', 'name': 'manager', 'dockerUrl': 'http://manager:3003'}
    for snapshot, config in [(reader, {'services': {'managers': [{'url': manager['dockerUrl'], 'token': 'test-token'}]}, 'stream': {'enabled': True}}),
                             (manager, {'subscriptions': {'readers': []}})]:
        path = tmp_path / snapshot['id'] / 'config/config.json'
        docker.save_json(path, config)
    async def snapshot(identifier):
        return {'reader': reader, 'manager': manager}[identifier]
    calls = []
    async def run(*args, **_):
        calls.append(args)
        return docker.json.dumps([{'Config': {'Env': ['API_TOKEN_MANAGER=test-token']}}]) if args[0] == 'inspect' else ''
    controller.snapshot = snapshot
    controller.run = run
    result = asyncio.run(controller.connection_action({'sourceId': 'reader', 'targetId': 'manager', 'transport': 'sse'}))
    assert result['transport'] == 'sse'
    assert docker.json.loads((tmp_path / 'reader/config/config.json').read_text())['services']['managers'] == []
    assert docker.json.loads((tmp_path / 'manager/config/config.json').read_text())['subscriptions']['readers'] == [reader['dockerUrl']]
    assert [call[1] for call in calls if call[0] == 'restart'] == ['reader-container', 'manager-container']


def test_compose_connection_preserves_mounted_config_inode(tmp_path, monkeypatch):
    monkeypatch.setattr(docker, 'ROOT', tmp_path)
    folder = tmp_path / 'deploy/docker'
    folder.mkdir(parents=True)
    configs = {'reader': {'services': {'managers': []}, 'stream': {'enabled': True}},
               'manager': {'subscriptions': {'readers': []}}}
    snapshots = {}
    for kind, config in configs.items():
        (folder / f'{kind}.json').write_text(docker.json.dumps(config))
        snapshots[f'compose-{kind}'] = {'id': f'compose-{kind}', 'kind': kind, 'container': kind,
                                        'name': kind, 'dockerUrl': f'http://{kind}:{docker.PORTS[kind]}', 'compose': True}
    before = {kind: (folder / f'{kind}.json').stat().st_ino for kind in configs}
    controller = object.__new__(docker.DockerController)
    controller.lock = asyncio.Lock()
    async def snapshot(identifier):
        return snapshots[identifier]
    async def run(*args, **_):
        if args[0] == 'inspect':
            kind = args[1]
            return docker.json.dumps([{'Config': {'Env': ['API_TOKEN_MANAGER=manager-token']},
                                       'Mounts': [{'Source': str(folder / f'{kind}.json'),
                                                   'Destination': f'/app/{kind}/config.json'}]}])
        return ''
    controller.snapshot = snapshot
    controller.run = run
    asyncio.run(controller.connection_action({'sourceId': 'compose-reader', 'targetId': 'compose-manager', 'transport': 'http'}))
    assert {kind: (folder / f'{kind}.json').stat().st_ino for kind in configs} == before
    reader = docker.json.loads((folder / 'reader.json').read_text())
    assert reader['services']['managers'] == [{'url': 'http://manager:3003', 'token': 'manager-token'}]


def test_compose_configuration_edits_mounted_file_and_restores_masked_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(docker, 'ROOT', tmp_path)
    folder = tmp_path / 'deploy/docker'
    folder.mkdir(parents=True)
    path = folder / 'manager.json'
    original = {'server': {'host': '0.0.0.0', 'port': 3003}, 'managerId': 'before',
                'services': {'verifiers': [{'url': 'http://verifier:5000', 'token': 'secret'}]}}
    path.write_text(docker.json.dumps(original))
    inode = path.stat().st_ino
    controller = object.__new__(docker.DockerController)
    controller.lock = asyncio.Lock()
    async def compose_snapshot(_):
        return {'id': 'compose-manager', 'kind': 'manager', 'container': 'container-id',
                'serviceConfig': docker.redact(docker.json.loads(path.read_text()))}
    calls = []
    async def run(*args, **_):
        calls.append(args)
        if args[0] == 'inspect':
            return docker.json.dumps([{'Mounts': [{'Source': str(path), 'Destination': '/app/manager/config.json'}]}])
        return ''
    controller.compose_snapshot = compose_snapshot
    controller.run = run
    edited = docker.redact(original)
    edited['managerId'] = 'after'
    result = asyncio.run(controller.action('compose-manager', {'action': 'config', 'config': edited}))
    assert result['serviceConfig']['managerId'] == 'after'
    assert path.stat().st_ino == inode
    assert docker.json.loads(path.read_text())['services']['verifiers'][0]['token'] == 'secret'
    assert ('restart', 'container-id') in calls
