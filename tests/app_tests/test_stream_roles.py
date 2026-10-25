"""Own streams, subscriptions and targeted outputs are independent."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from flask import Flask
import pytest


@pytest.fixture(autouse=True)
def initialize_manager_logger(tmp_path):
    from manager_support.logger import Logger
    Logger.init(str(tmp_path / "logs"), service="manager", logging=False, verbose=False, dev=False)


def test_manager_own_stream_without_outputs():
    from server import ManagerServer
    app = Flask(__name__)
    config = SimpleNamespace(stream_enabled=True, output_verifiers=False, output_storages=False,
        api_token_manager='m', api_token_verifier='v', api_token_storage='s')
    server = ManagerServer(app, config)
    assert app.test_client().get('/stream/verifier').status_code == 404
    response = app.test_client().get('/stream', headers={'Authorization':'Bearer m'}, buffered=False)
    assert b'connected' in next(response.response)
    server.publish_captured({'key':'own','value':{'status':'Captured'}})
    assert b'own' in next(response.response)
    response.close()


def test_targeted_outputs_without_own_stream():
    from server import ManagerServer
    app = Flask(__name__)
    config = SimpleNamespace(stream_enabled=False, output_verifiers=True, output_storages=False,
        api_token_manager='m', api_token_verifier='v', api_token_storage='s')
    server = ManagerServer(app, config)
    assert app.test_client().get('/stream').status_code == 404
    response = app.test_client().get('/stream/verifier', headers={'Authorization':'Bearer v', 'X-Phonendo-Service-URL':'http://v'}, buffered=False)
    next(response.response)
    server.publish_captured({'key':'target','value':{}})
    assert b'target' in next(response.response)
    response.close()


def test_subscriptions_not_controlled_by_own_stream(tmp_path, monkeypatch):
    from config import ManagerConfig
    monkeypatch.setenv('MANAGER_PASSWORD','test-secret')
    path = tmp_path/'config.json'
    path.write_text(json.dumps({'stream':{'enabled':False}, 'subscriptions':{
        'readers':['http://r'], 'verifiers':['http://v'], 'storages':['http://s']}}))
    config = ManagerConfig(path)
    assert config.stream_enabled is False
    assert config.reader_subscriptions == ['http://r']
    assert config.verifier_subscriptions == ['http://v']
    assert config.storage_subscriptions == ['http://s']


def test_storage_stream_after_write(tmp_path, monkeypatch):
    from test_storage import load_storage
    config = tmp_path/'config.json'
    config.write_text(json.dumps({'stream':{'enabled':True},'subscriptions':{'managers':[]}}))
    monkeypatch.setenv('STORAGE_CONFIG_PATH',str(config))
    storage = load_storage(tmp_path,monkeypatch)
    response = storage.app.test_client().get('/stream',headers={'Authorization':'Bearer token_storage'},buffered=False)
    next(response.response)
    message = {'key':'stored-event','value':{'status':'Verified','verifierSign':'signature','payload':{'value':1}}}
    try:
        result=storage.app.test_client().post('/events',json={'token':'token_storage','message':message})
        assert result.status_code == 200
        event=next(response.response)
        assert b'stored-event' in event
        assert storage.my_db.read('stored-event') == message['value']
    finally:
        response.close()
        storage.manager_subscriptions.close()
        storage.my_db.close()


def test_manager_does_not_store_storage_confirmations():
    from core import ManagerCore
    client = MagicMock()
    core = ManagerCore(client, MagicMock(),10,5)
    try:
        core.on_storage_stream_event('http://s',{'key':'stored','value':{'status':'Verified'}})
        client.store_event.assert_not_called()
    finally:
        core.close()


def test_manager_correlates_verifier_subscription_results():
    import copy
    from core import ManagerCore
    client, server = MagicMock(), MagicMock()
    client.config = SimpleNamespace(storage_url_list=['http://storage'])
    core = ManagerCore(client,server,10,5)
    original = {'key':'own-event','value':{'status':'Captured','deviceId':'d','payload':{'value':1},'managerHash':'hash'}}
    core.stream_pending['own-event'] = {'message':original,'sources':set()}
    verified = copy.deepcopy(original)
    verified['value'].update(status='Verified',verifierSign='signature')
    client.store_event.side_effect = lambda message, **kwargs: message
    try:
        foreign = copy.deepcopy(verified)
        foreign['key'] = 'other-manager-event'
        core.on_verifier_stream_event('http://v',foreign)
        tampered = copy.deepcopy(verified)
        tampered['value']['payload']['value'] = 2
        core.on_verifier_stream_event('http://v',tampered)
        client.store_event.assert_not_called()
        core.on_verifier_stream_event('http://v',verified)
        assert client.store_event.call_count == 1
        core.on_verifier_stream_event('http://v',verified)
        assert client.store_event.call_count == 1
    finally:
        core.close()
