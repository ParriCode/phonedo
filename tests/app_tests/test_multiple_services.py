import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import requests

ROOT = Path(__file__).resolve().parents[2]


def test_verifier_jobs_are_independent():
    from core import ManagerCore
    client = SimpleNamespace(config=SimpleNamespace(verifier_url_list=['http://v1', 'http://v2'],
                                                     stream=False, stream_verifiers=False))
    core = ManagerCore(client, None, 10, 5)
    calls = []
    def attempt(job, *, enqueue):
        calls.append(job)
        return {'eventId': job['message']['key'], 'status': 'Pending' if len(calls) == 1 else 'Verified'}, 202 if len(calls) == 1 else 200
    with patch.object(core, 'attempt_event', side_effect=attempt):
        result, status = core.submit_observation({'readerId':'r', 'deviceId':'d',
            'payload':{'value':1}, 'payloadFormat':'application/json', 'eventType':'observation'})
    assert status == 207
    assert [entry['httpStatus'] for entry in result['results']] == [202, 200]
    assert calls[0]['verifier'] == 'http://v1'
    assert calls[1]['verifier'] == 'http://v2'
    assert calls[0]['message']['key'] != calls[1]['message']['key']
    core.close()


def test_storage_retry_skips_confirmed_destinations():
    from client import ManagerClient
    config = SimpleNamespace(storage_url_list=['http://s1','http://s2'], api_token_storage='token')
    client = ManagerClient(config)
    message = {'key':'event', 'value':{'status':'Verified'}}
    completed = set()
    with patch.object(client, '_post', side_effect=[message, requests.Timeout()]):
        try:
            client.store_event(message, completed)
        except requests.Timeout:
            pass
    assert completed == {'http://s1'}
    with patch.object(client, '_post', return_value=message) as post:
        client.store_event(message, completed)
    assert post.call_count == 1
    assert post.call_args.args[0] == 'http://s2/events'


def test_reader_sends_to_other_managers_after_one_fails():
    from reader_server import ManagerOutput
    from urllib.error import URLError
    output = ManagerOutput([{'url':'http://m1','token':'a'}, {'url':'http://m2','token':'b'}])
    from unittest.mock import MagicMock
    response = MagicMock()
    response.__enter__.return_value.status = 200
    with patch('reader_server.manager_output.urlopen', side_effect=[URLError('offline'), response]) as send:
        result = output._send('/newEvent', {'payload':{'value':1}})
    assert send.call_count == 2
    assert 'error' in result[0]
    assert result[1]['status'] == 200


def test_timeout_retries_only_its_verifier(monkeypatch):
    import copy
    from unittest.mock import MagicMock
    from core import ManagerCore
    monkeypatch.setenv('MANAGER_PASSWORD', 'test-secret')
    client = MagicMock()
    client.config = SimpleNamespace(verifier_url_list=['http://slow', 'http://fast'],
                                    stream=False, stream_verifiers=False)
    calls = []
    retry = False
    def verify(message, target=None):
        calls.append(target)
        if target == 'http://slow' and not retry:
            raise requests.Timeout()
        verified = copy.deepcopy(message)
        verified['value'].update(status='Verified', verifierSign='test-signature')
        return {'verified': True, 'message': verified}
    client.verify_event.side_effect = verify
    client.store_event.side_effect = lambda message, **kwargs: message
    core = ManagerCore(client, MagicMock(), 10, 60)
    result, status = core.submit_observation({'readerId':'r', 'deviceId':'d',
            'payload':{'value':1}, 'payloadFormat':'application/json', 'eventType':'observation'})
    assert status == 207
    assert len(core.pending_events) == 1
    assert client.store_event.call_count == 1
    retry = True
    core.pending_events.retry_once()
    assert calls.count('http://fast') == 1
    assert calls.count('http://slow') == 2
    assert len(core.pending_events) == 0
    assert client.store_event.call_count == 2
    core.close()
