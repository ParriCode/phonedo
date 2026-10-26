"""Gestión local del panel: acciones reales, tokens y separación de orígenes."""
import asyncio
import importlib.util
from pathlib import Path

from aiohttp import ClientSession
from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('web_runtime_test', ROOT / 'tools/web_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
HEADERS = {'X-Phonendo-Control': 'local'}


def test_reader_devices_pulses_and_live_configuration(monkeypatch):
    monkeypatch.setenv('PHONENDO_WEB_NO_BROWSER', '1')
    async def check():
        async with TestClient(TestServer(runtime.create_app())) as client:
            response = await client.post('/api/local/readers', headers=HEADERS, json={
                'id': 'reader-test', 'config': {'readerId': 'reader-test', 'token': 'private-reader', 'streamEnabled': False}})
            assert response.status == 201
            created = await response.json()
            assert 'private-reader' not in str(created)
            url = created['url']
            endpoint = '/api/local/readers/reader-test'
            async def command(body):
                response = await client.post(endpoint, headers=HEADERS, json=body)
                assert response.status == 200, await response.text()
                return await response.json()
            await command({'action': 'device', 'deviceId': 'band'})
            await command({'action': 'sensor', 'deviceId': 'band', 'sensorId': 'pulse',
                           'property': 'heart-rate', 'unit': 'bpm', 'procedure': 'manual-pulse'})
            result = await command({'action': 'pulse', 'deviceId': 'band', 'sensorId': 'pulse', 'value': 105, 'count': 32})
            observations = [event for event in result['events'] if event['message'] == 'observation_created']
            assert len(observations) == 32
            assert len({event['observationId'] for event in observations}) == 32
            async with ClientSession() as session:
                assert (await session.get(url + '/metadata')).status == 401
                headers = {'Authorization': 'Bearer private-reader'}
                assert (await session.get(url + '/stream', headers=headers)).status == 409
                result = await command({'action': 'config', 'config': {**created['config'], 'streamEnabled': True}})
                metadata = await (await session.get(url + '/metadata', headers=headers)).json()
                assert metadata['capabilities']['stream'] is True
                result = await command({'action': 'config', 'config': {**result['config'], 'token': 'new-token'}})
                assert (await session.get(url + '/metadata', headers=headers)).status == 401
                assert (await session.get(url + '/metadata', headers={'Authorization': 'Bearer new-token'})).status == 200
            assert (await client.delete(endpoint, headers=HEADERS)).status == 200
            assert (await client.get(endpoint)).status == 404
    asyncio.run(check())


def test_control_rejects_other_origins_and_public_proxies(monkeypatch):
    monkeypatch.setenv('PHONENDO_WEB_NO_BROWSER', '1')
    async def check():
        async with TestClient(TestServer(runtime.create_app())) as client:
            assert (await client.post('/api/local/readers', json={})).status == 403
            assert (await client.post('/api/local/readers', headers={**HEADERS, 'Origin': 'https://other.test'}, json={})).status == 403
            assert (await client.post('/api/local/probe', headers=HEADERS,
                                      json={'url': 'http://8.8.8.8', 'path': '/logs'})).status == 400
            assert (await client.post('/api/local/probe', headers=HEADERS,
                                      json={'url': 'http://127.0.0.1', 'path': '/config'})).status == 400
            response = await client.get('/operator.html', headers={'If-Modified-Since': 'Wed, 01 Jan 2100 00:00:00 GMT'})
            assert response.status == 200
            assert response.headers['Cache-Control'] == 'no-store'
    asyncio.run(check())


def test_container_inventory_returns_only_observed_snapshots(monkeypatch):
    import web_docker
    monkeypatch.setenv('PHONENDO_WEB_NO_BROWSER', '1')
    async def compose(self):
        return [{'id': 'compose-publisher', 'kind': 'publisher', 'name': 'phonendo-publisher-1',
                 'image': 'phonendo-publisher:latest', 'state': 'running', 'url': 'http://127.0.0.1:7105'}]
    monkeypatch.setattr(web_docker.DockerController, 'compose_snapshots', compose)
    async def check():
        async with TestClient(TestServer(runtime.create_app())) as client:
            response = await client.get('/api/local/containers')
            assert response.status == 200
            rows = await response.json()
            assert [row['id'] for row in rows] == ['compose-publisher']
            assert rows[0]['image'] == 'phonendo-publisher:latest'
    asyncio.run(check())


def test_image_inventory_and_actions_use_the_local_controller(monkeypatch):
    import web_docker
    monkeypatch.setenv('PHONENDO_WEB_NO_BROWSER', '1')
    async def images(self):
        return [{'id': 'image-reader', 'kind': 'reader', 'image': 'phonendo-reader:latest', 'imageOnly': True}]
    async def action(self, kind, operation, progress, source, reference):
        assert (kind, operation, source, reference) == ('reader', 'remove', 'compose', 'phonendo-reader:latest')
        return {'removed': True}
    monkeypatch.setattr(web_docker.DockerController, 'image_snapshots', images)
    monkeypatch.setattr(web_docker.DockerController, 'image_action', action)
    async def check():
        async with TestClient(TestServer(runtime.create_app())) as client:
            response = await client.get('/api/local/images')
            assert (await response.json())[0]['image'] == 'phonendo-reader:latest'
            response = await client.delete('/api/local/images/compose-reader', headers=HEADERS,
                                           json={'image': 'phonendo-reader:latest'})
            operation = await response.json()
            await asyncio.sleep(0)
            state = await (await client.get('/api/local/operations/' + operation['id'])).json()
            assert state['result'] == {'removed': True}
    asyncio.run(check())


def test_connection_route_applies_a_real_controller_operation(monkeypatch):
    import web_docker
    monkeypatch.setenv('PHONENDO_WEB_NO_BROWSER', '1')
    async def action(self, body, progress):
        assert body == {'sourceId': 'compose-reader', 'targetId': 'compose-manager', 'transport': 'sse'}
        return body
    monkeypatch.setattr(web_docker.DockerController, 'connection_action', action)
    async def check():
        async with TestClient(TestServer(runtime.create_app())) as client:
            response = await client.post('/api/local/connections', headers=HEADERS,
                                         json={'sourceId': 'compose-reader', 'targetId': 'compose-manager', 'transport': 'sse'})
            assert response.status == 202
            operation = await response.json()
            await asyncio.sleep(0)
            result = await (await client.get('/api/local/operations/' + operation['id'])).json()
            assert result['result']['transport'] == 'sse'
    asyncio.run(check())
