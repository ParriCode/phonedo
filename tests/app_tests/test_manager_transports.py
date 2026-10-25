"""A service pair has only one delivery transport, independently of other peers."""
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests
from flask import Flask

from client import ManagerClient
from core import ManagerCore
from server import ManagerServer, register_routes
from test_manager_reader_stream import Response


@pytest.fixture
def core(tmp_path):
    from manager_support.logger import Logger
    Logger.init(str(tmp_path), service='manager', logging=False, verbose=False, dev=False)
    instance = ManagerCore(MagicMock(), MagicMock(), 10, 60)
    yield instance
    instance.close()


@pytest.mark.parametrize('service', ['verifier', 'storage'])
def test_http_blocks_same_peer_sse_but_allows_other_peers(core, service):
    config = SimpleNamespace(stream_enabled=True, output_verifiers=True, output_storages=True,
        api_token_manager='m', api_token_verifier='v', api_token_storage='s',
        verifier_url_list=['http://HTTP-PEER:80/'], storage_url_list=[{'url':'http://HTTP-PEER:80/'}])
    app = Flask(__name__)
    server = ManagerServer(app, config)
    http = app.test_client()
    path = '/stream/' + service
    headers = {'Authorization': 'Bearer ' + getattr(config, 'api_token_' + service),
               'X-Phonendo-Service-URL': 'http://http-peer'}
    with patch('server.Logger.warning') as log:
        assert http.get(path, headers=headers).status_code == 409
        assert log.call_args.kwargs['selected'] == 'http'
    assert not server._connections
    headers['X-Phonendo-Service-URL'] = 'http://sse-peer'
    response = http.get(path, headers=headers, buffered=False)
    assert response.status_code == 200
    assert b'connected' in next(response.response)
    assert http.get(path, headers=headers).status_code == 409
    stream = getattr(server, service + '_stream')
    stream.publish({'key': 'event', 'value': {'status': 'Verified'}})
    assert b'event' in next(response.response)
    response.close()
    assert not server._connections
    reconnected = http.get(path, headers=headers, buffered=False)
    assert reconnected.status_code == 200
    reconnected.close()
    assert http.get(path, headers={'Authorization': headers['Authorization']}).status_code == 400
    assert http.get(path, headers={'X-Phonendo-Service-URL':'http://sse-peer'}).status_code == 401


def test_reader_http_first_never_opens_sse(core):
    assert core.prefer_http('r')
    client = ManagerClient(SimpleNamespace(api_token_reader='token'))
    metadata = Response({'readerId':'r', 'capabilities':{'stream': True}})
    with patch('client.requests.get', return_value=metadata) as get:
        assert client.consume_reader_stream('http://r', core.on_reader_stream_event,
                                            threading.Event(), core) is False
    assert get.call_count == 1
    assert get.call_args.args[0].endswith('/metadata')


def test_reader_sse_first_rejects_http_and_can_reconnect(core, monkeypatch):
    monkeypatch.setenv('API_TOKEN_MANAGER', 'token')
    app = Flask(__name__)
    register_routes(app, core)
    assert core.acquire_reader_stream('r')
    core.activate_reader_stream('r')
    body = {'token':'token', 'readerId':'r', 'deviceId':'d', 'payload':{'value':1},
            'payloadFormat':'application/json', 'eventType':'observation'}
    with patch.object(core, 'submit_observation') as submit:
        assert app.test_client().post('/newEvent', json=body).status_code == 409
        submit.assert_not_called()
    assert not core.acquire_reader_stream('r')
    core.release_reader_stream('r')
    assert not core.prefer_http('r')
    assert core.acquire_reader_stream('r')
    assert core.prefer_http('another-reader')


def test_failed_reader_connection_releases_reservation(core):
    client = ManagerClient(SimpleNamespace(api_token_reader='token'))
    metadata = Response({'readerId':'r', 'capabilities':{'stream': True}})
    with patch('client.requests.get', side_effect=[metadata, requests.ConnectionError('offline')]):
        with pytest.raises(requests.ConnectionError):
            client.consume_reader_stream('http://r', core.on_reader_stream_event, threading.Event(), core)
    assert core.prefer_http('r')


def test_reader_transport_claim_is_atomic(core):
    barrier = threading.Barrier(2)
    def claim(fn):
        barrier.wait()
        return fn('r')
    with ThreadPoolExecutor(2) as pool:
        http = pool.submit(claim, core.prefer_http)
        sse = pool.submit(claim, core.acquire_reader_stream)
        assert sorted([http.result(), sse.result()]) == [False, True]


def test_manager_does_not_subscribe_to_http_peers_or_duplicate_urls(core):
    config = SimpleNamespace(verifier_url_list=['http://v1'], storage_url_list=['http://s1'],
        verifier_subscriptions=['http://v1/', 'http://v2', {'url':'http://v2:80/'}],
        storage_subscriptions=['http://s1', 'http://s2', 'http://s2/'],
        api_token_verifier='v', api_token_storage='s')
    client = ManagerClient(config)
    with patch.object(client, 'start_reader_subscriptions', return_value=MagicMock()), \
         patch('manager_support.stream_client.StreamClient') as streams:
        stop = client.start_subscriptions(core)
        assert [call.args[0][0]['url'] for call in streams.call_args_list] == [
            'http://v2/stream', 'http://s2/stream']
        stop()


def test_duplicate_http_targets_are_sent_once(core):
    config = SimpleNamespace(storage_url_list=['http://s', {'url':'http://s:80/'}],
                             api_token_storage='s')
    client = ManagerClient(config)
    message = {'key':'event', 'value':{}}
    with patch.object(client, '_post', return_value=message) as post:
        client.store_event(message)
        assert post.call_count == 1
    core.client.config = SimpleNamespace(verifier_url_list=['http://v', 'http://v:80/'],
                                        stream_enabled=False, output_verifiers=False)
    with patch.object(core, 'attempt_event', return_value=({}, 200)) as attempt:
        core.submit_observation({'readerId':'r', 'deviceId':'d', 'payload':{'value':1},
                                 'payloadFormat':'application/json', 'eventType':'observation'})
        assert attempt.call_count == 1


def test_duplicate_reader_subscription_starts_one_worker(core):
    client = ManagerClient(SimpleNamespace(reader_subscriptions=['http://r', {'url':'http://r:80/'}]))
    with patch('threading.Thread') as worker:
        stop = client.start_reader_subscriptions(core.on_reader_stream_event, core)
        assert worker.call_count == 1
        stop()


@pytest.mark.parametrize('service', ['verifier', 'storage'])
def test_subscriber_sends_its_identity_and_token(service, monkeypatch, core):
    import importlib
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'apps' / service))
    module = importlib.import_module(service + '_support.stream_client')
    received = []
    def on_event(message):
        received.append(message)
        client.stopped.set()
    client = module.StreamClient([], 'default', on_event, service_url='http://peer:5000')
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_lines.return_value = [b'event: observation', b'data: {"key":"event"}', b'']
    with patch.object(module.requests, 'get', return_value=response) as get:
        client._run({'url':'http://manager/stream/' + service, 'token':'specific-token'})
    assert get.call_args.kwargs['headers'] == {
        'Authorization':'Bearer specific-token', 'X-Phonendo-Service-URL':'http://peer:5000'}
    assert received == [{'key':'event'}]
