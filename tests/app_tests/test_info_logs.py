"""Información de conexiones y mensajes públicos, sin autenticación."""
import asyncio
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(params=['manager', 'verifier', 'storage'])
def service(request, tmp_path, monkeypatch):
    kind = request.param
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({
        'services': {'verifiers': ['http://verifier'], 'storages': ['http://storage']},
        'stream': {'enabled': True},
        'outputStreams': {'verifiers': True, 'storages': True},
        'subscriptions': {}}))
    monkeypatch.setenv(kind.upper() + '_CONFIG_PATH', str(config))
    monkeypatch.setenv('MANAGER_PASSWORD', 'private-password')
    for name in ('MANAGER', 'VERIFIER', 'STORAGE'):
        monkeypatch.setenv('API_TOKEN_' + name, 'private-token')
    monkeypatch.setenv('PHONENDO_DB_PATH', str(tmp_path / 'db'))
    monkeypatch.setenv('PHONENDO_LOGS_DIR', str(tmp_path / 'logs'))
    monkeypatch.setenv('PHONENDO_LOGGING', 'false')
    monkeypatch.setenv('PHONENDO_DEV', 'true')
    entry = 'main.py' if kind == 'storage' else kind + '.py'
    spec = importlib.util.spec_from_file_location('info_test_' + kind, ROOT / 'apps' / kind / entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield kind, module
    if kind == 'manager':
        module.core.close()
    else:
        module.manager_subscriptions.close()
    if kind == 'storage':
        module.my_db.close()


def test_public_lists_and_private_business_routes(service):
    kind, module = service
    client = module.app.test_client()
    for route in ('/info', '/logs'):
        response = client.get(route)
        assert response.status_code == 200
        assert isinstance(response.json, list)
        assert 'private-token' not in response.text
        assert 'private-password' not in response.text
    for item in client.get('/info').json:
        assert set(item) == {'peer', 'transport'}
        assert item['transport'] in ('http', 'sse')
    module.Logger.warning('connection_failed', error='private-token', payload={'secret':'private-password'})
    latest = client.get('/logs').json[-1]
    assert (json.loads(latest)['message'] if kind != 'storage' else latest) == 'connection_failed'
    assert client.get('/logs').json == client.get('/logs').json
    private_route = {'manager':'/newEvent', 'verifier':'/verify', 'storage':'/events'}[kind]
    assert client.post(private_route, json={}).status_code == 401


def test_logs_are_bounded_messages(service):
    _, module = service
    for index in range(205):
        module.Logger.info('event_' + str(index))
    logs = module.app.test_client().get('/logs').json
    assert len(logs) == 200
    assert (json.loads(logs[0])['message'] if module.Logger.instance().service != 'storage' else logs[0]) == 'event_5'
    assert (json.loads(logs[-1])['message'] if module.Logger.instance().service != 'storage' else logs[-1]) == 'event_204'
    assert all(isinstance(item, str) for item in logs)


def test_sse_incoming_appears_and_disappears(service):
    _, module = service
    client = module.app.test_client()
    stream = client.get('/stream', headers={'Authorization':'Bearer private-token'}, buffered=False)
    assert b'connected' in next(stream.response)
    assert {'peer':'127.0.0.1', 'transport':'sse'} in client.get('/info').json
    stream.close()
    assert {'peer':'127.0.0.1', 'transport':'sse'} not in client.get('/info').json


def test_sse_outgoing_uses_active_subscriptions_only(service):
    kind, module = service
    if kind == 'manager':
        from manager_support.stream_client import StreamClient
        subscription = StreamClient(['http://peer/stream'], 'token', lambda _: None)
        module.manager_client.subscriptions.append(subscription)
    else:
        subscription = module.manager_subscriptions
    client = module.app.test_client()
    row = {'peer':'http://peer', 'transport':'sse'}
    assert row not in client.get('/info').json
    subscription.connected.add('http://peer/stream')
    assert row in client.get('/info').json
    subscription.connected.clear()
    assert row not in client.get('/info').json


def test_http_connections(service):
    kind, module = service
    client = module.app.test_client()
    if kind == 'manager':
        assert {'peer':'http://verifier', 'transport':'http'} in client.get('/info').json
        assert {'peer':'http://storage', 'transport':'http'} in client.get('/info').json
        module.core.prefer_http('reader-one')
        assert {'peer':'reader-one', 'transport':'http'} in client.get('/info').json
    elif kind == 'verifier':
        with patch.object(module, 'verify_message', return_value=({'verified':False}, 422)):
            assert client.post('/verify', json={'token':'private-token'}).status_code == 422
        assert {'peer':'127.0.0.1', 'transport':'http'} in client.get('/info').json
    else:
        assert client.post('/events', json={'token':'private-token',
                           'message':{'key':'one', 'value':{}}}).status_code == 200
        assert {'peer':'127.0.0.1', 'transport':'http'} in client.get('/info').json


def test_reader_public_lists_and_authenticated_stream():
    from aiohttp.test_utils import TestClient, TestServer
    from reader_core import ReaderCore
    from reader_server import ReaderServer, ServerConfig, ManagerOutput
    async def check():
        output = ManagerOutput([{'url':'http://manager', 'token':'private-token'}])
        server = ReaderServer(ReaderCore('reader'), ServerConfig(enabled=True, token='private-token'),
                              outputs=(output,))
        async with TestClient(TestServer(server.app)) as client:
            response = await client.get('/info')
            assert response.status == 200
            assert await response.json() == [{'peer':'http://manager', 'transport':'http'}]
            logs = await client.get('/logs')
            assert logs.status == 200
            assert await logs.json() == ['reader_initialized']
            assert (await client.get('/stream')).status == 401
            stream = await client.get('/stream', headers={'Authorization':'Bearer private-token'})
            assert b'connected' in await stream.content.readline()
            assert {'peer':'127.0.0.1', 'transport':'sse'} in await (await client.get('/info')).json()
            server.stream.close()
            await stream.read()
            assert {'peer':'127.0.0.1', 'transport':'sse'} not in await (await client.get('/info')).json()
            assert await (await client.get('/logs')).json() == [
                'reader_initialized', 'stream_connected', 'stream_disconnected']
            from urllib.error import URLError
            with patch('reader_server.manager_output.urlopen', side_effect=URLError('private-token')):
                output._send('/newEvent', {'payload': {'private':'reading'}})
            messages = await (await client.get('/logs')).json()
            assert messages[-1] == 'manager_http_delivery_failed'
            assert 'private-token' not in json.dumps(messages)
    asyncio.run(check())


@pytest.mark.parametrize('kind', ['manager', 'verifier', 'storage'])
def test_stream_client_tracks_lifetime(kind, monkeypatch, tmp_path):
    import importlib
    monkeypatch.syspath_prepend(str(ROOT / 'apps' / kind))
    module = importlib.import_module(kind + '_support.stream_client')
    module.Logger.init(str(tmp_path), logging=False)
    client = module.StreamClient([], '', lambda _: None)
    response = MagicMock()
    response.__enter__.return_value = response
    def lines(**kwargs):
        assert client.connected == {'http://peer/stream'}
        client.stopped.set()
        yield b': heartbeat'
    response.iter_lines.side_effect = lines
    with patch.object(module.requests, 'get', return_value=response):
        client._run('http://peer/stream')
    assert client.connected == set()
