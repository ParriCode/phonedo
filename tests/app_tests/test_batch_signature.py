"""Firma ed25519 del lote: Publisher -> Manager -> Verifier."""
import base64
import importlib.util
import json
import os
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
ZERO_ACCOUNT = 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF'
ENV = {'API_TOKEN_VERIFIER': 'verify', 'API_TOKEN_MANAGER': 'manager', 'MANAGER_PASSWORD': 'test-only-secret',
       'PHONENDO_LOGGING': 'false', 'PHONENDO_VERBOSE': 'false'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def verifier(tmp_path):
    key = Ed25519PrivateKey.generate()
    key_file = tmp_path / 'signing_key.json'
    key_file.write_text(json.dumps({'kty': 'OKP', 'crv': 'Ed25519',
                                    'd': base64.urlsafe_b64encode(key.private_bytes_raw()).decode().rstrip('=')}))
    config = tmp_path / 'verifier.json'
    config.write_text(json.dumps({'keyPath': str(key_file)}))
    with patch.dict(os.environ, dict(ENV, VERIFIER_CONFIG_PATH=str(config))):
        module = load('verifier_batch_test', 'apps/verifier/verifier.py')
        module.public_key = key.public_key()
        yield module
        module.manager_subscriptions.close()


def captured(verifier, reading, device_id='sensor-1'):
    message = {'key': str(uuid.uuid4()), 'value': {
        'schemaVersion': 'phonendo.event.v1', 'eventType': 'observation', 'readerId': 'reader',
        'managerId': 'manager-default', 'observationId': str(uuid.uuid4()),
        'deviceId': device_id, 'payloadFormat': 'application/json', 'payload': {'simple_result': reading},
        'status': 'Captured', 'creationDatetime': int(time.time() * 1000)}}
    message['value']['managerHash'] = verifier.sign_event(message)
    return message


def verify_batch(verifier, readings):
    keys = []
    for reading in readings:
        message = captured(verifier, reading)
        result, status = verifier.verify_message(message)
        assert status == 200
        keys.append(message['key'])
    return keys


def test_poseidon_matches_circuit_commitment():
    sys.path.insert(0, str(ROOT / 'apps/verifier'))
    from verifier_support.poseidon import batch_commitment

    session = json.loads((ROOT / 'circuits/inputs/session.json').read_text())
    commitment = batch_commitment(session['readings'], session['salt'], session['sessionId'])
    assert f'{commitment:064x}' == '182e03dee1287a69bf32b2cf9e0b0a433a642ea9dcc287e30100bccdb4481f2e'


def test_verifier_signs_batch_with_its_own_readings(verifier):
    from verifier_support.poseidon import batch_commitment

    readings = [100 + i for i in range(32)]
    keys = verify_batch(verifier, readings)
    body = {'token': 'verify', 'sessionId': 7, 'salt': '123', 'patient': ZERO_ACCOUNT, 'eventKeys': keys,
            'verifierId': verifier.verifier_id, 'managerId': 'manager-default', 'readerId': 'reader'}
    with patch.dict(os.environ, ENV):
        response = verifier.app.test_client().post('/signBatch', json=body)
    assert response.status_code == 200
    reply = response.get_json()
    assert reply['commitment'] == f'{batch_commitment(readings, 123, 7):064x}'
    message = bytes.fromhex(reply['commitment']) + (7).to_bytes(32, 'big') + bytes(32) + bytes.fromhex(verifier.verifier_id)
    verifier.public_key.verify(bytes.fromhex(reply['signature']), message)


def test_event_and_batch_signatures_share_one_ed25519_key(verifier):
    result, status = verifier.verify_message(captured(verifier, 100))
    assert status == 200
    message = result['message']
    assert message['value']['verifierId'] == verifier.verifier_id
    signature = bytes.fromhex(message['value'].pop('verifierSign'))
    verifier.public_key.verify(signature, verifier.canonical_json(message).encode())


def test_verifier_rejects_wrong_identity_and_cross_manager_batch(verifier):
    keys = verify_batch(verifier, [100] * 32)
    body = {'token': 'verify', 'sessionId': 7, 'salt': '1', 'patient': ZERO_ACCOUNT,
            'eventKeys': keys, 'managerId': 'manager-default', 'readerId': 'reader',
            'verifierId': verifier.verifier_id}
    with patch.dict(os.environ, ENV):
        client = verifier.app.test_client()
        assert client.post('/signBatch', json=dict(body, verifierId='other')).status_code == 422
        assert client.post('/signBatch', json=dict(body, managerId='other')).status_code == 422
        event = captured(verifier, 101)
        event['value']['managerId'] = 'manager-b'
        event['value']['managerHash'] = verifier.sign_event(event)
        result, status = verifier.verify_message(event)
        assert status == 200
        assert result['message']['value']['managerId'] == 'manager-b'
        assert client.post('/signBatch', json=dict(body, eventKeys=keys[:31] + [event['key']])).status_code == 422


def test_verifier_rejects_unknown_events_and_bad_token(verifier):
    keys = verify_batch(verifier, [100] * 31) + [str(uuid.uuid4())]
    body = {'token': 'verify', 'sessionId': 7, 'salt': '1', 'patient': ZERO_ACCOUNT, 'eventKeys': keys,
            'verifierId': verifier.verifier_id, 'managerId': 'manager-default', 'readerId': 'reader'}
    with patch.dict(os.environ, ENV):
        client = verifier.app.test_client()
        assert client.post('/signBatch', json=body).status_code == 422
        assert client.post('/signBatch', json=dict(body, eventKeys=keys[:31] * 2)).status_code == 422
        assert client.post('/signBatch', json=dict(body, token='other')).status_code == 401


def test_manager_forwards_sign_batch_to_verifier():
    sys.path.insert(0, str(ROOT / 'apps/manager'))
    with patch.dict(os.environ, ENV):
        manager = load('manager_batch_test', 'apps/manager/manager.py')
        try:
            manager.manager_config.verifier_url_list = ['http://verifier:5000']
            manager.manager_config.manager_id = 'manager-default'
            reply = {'commitment': 'ab' * 32, 'signature': 'cd' * 64}
            body = {'sessionId': 7, 'salt': '1', 'patient': ZERO_ACCOUNT, 'eventKeys': ['k'],
                    'verifierId': 'verifier-v', 'managerId': 'manager-default', 'readerId': 'reader'}
            metadata = MagicMock(json=MagicMock(return_value={'verifierId': 'verifier-v'}))
            with patch.object(manager.manager_client, '_post', return_value=reply) as post, patch('requests.get', return_value=metadata):
                client = manager.app.test_client()
                assert client.post('/signBatch', json=dict(body, token='other')).status_code == 401
                response = client.post('/signBatch', json=dict(body, token='manager'))
            assert response.status_code == 200 and response.get_json() == reply
            post.assert_called_once_with('http://verifier:5000/signBatch', dict(body, token='verify'))
        finally:
            manager.core.close()


def test_publisher_asks_manager_and_checks_commitment():
    sys.path.insert(0, str(ROOT / 'apps/publisher'))
    from publisher_support.signer import ManagerSigner

    signer = ManagerSigner('http://manager:3003/', 'manager')
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    key = Ed25519PrivateKey.generate()
    verifier_id = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    batch = {'sessionId': 7, 'salt': '1', 'eventKeys': ['k'],
             'verifierId': verifier_id, 'managerId': 'manager-default', 'readerId': 'reader'}
    signature = key.sign(bytes.fromhex('ab' * 32) + (7).to_bytes(32, 'big') + bytes(32) + bytes.fromhex(verifier_id)).hex()
    reply = MagicMock(ok=True, json=MagicMock(return_value={'commitment': 'ab' * 32, 'signature': signature, 'verifierId': verifier_id}))
    with patch('requests.post', return_value=reply) as post:
        assert signer.sign(batch, 'ab' * 32, ZERO_ACCOUNT) == signature
        with pytest.raises(ValueError, match='no coincide'):
            signer.sign(batch, 'ef' * 32, ZERO_ACCOUNT)
    assert post.call_args.args == ('http://manager:3003/signBatch',)
    assert post.call_args.kwargs['json'] == {'token': 'manager', 'sessionId': 7, 'salt': '1',
                                             'patient': ZERO_ACCOUNT, 'eventKeys': ['k'],
                                             'managerId': 'manager-default', 'readerId': 'reader', 'verifierId': verifier_id}


def test_account_key_checks_the_strkey():
    sys.path.insert(0, str(ROOT / 'apps/verifier'))
    from verifier_support.batch_signer import account_key

    assert account_key(ZERO_ACCOUNT) == bytes(32)
    with pytest.raises(ValueError):
        account_key(ZERO_ACCOUNT[:-1] + 'G')


def test_manager_selects_requested_verifier_among_several():
    from types import SimpleNamespace
    from client import ManagerClient
    client = ManagerClient(SimpleNamespace(
        verifier_url_list=['http://first', 'http://second'],
        verifier_subscriptions=[], api_token_verifier='token'))
    metadata = [MagicMock(json=MagicMock(return_value={'verifierId': identity}))
                for identity in ('first-id', 'second-id')]
    with patch('requests.get', side_effect=metadata), patch.object(client, '_post', return_value={'ok': True}) as post:
        assert client.sign_batch({'verifierId': 'second-id'}) == {'ok': True}
    assert post.call_args.args[0] == 'http://second/signBatch'


def test_publisher_rejects_forged_batch_signature():
    from publisher_support.signer import ManagerSigner
    key = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    verifier_id = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    batch = {'sessionId': 7, 'salt': '1', 'eventKeys': ['k'],
             'verifierId': verifier_id, 'managerId': 'manager', 'readerId': 'reader'}
    reply = MagicMock(ok=True, json=MagicMock(return_value={
        'commitment': 'ab' * 32, 'signature': '00' * 64, 'verifierId': verifier_id}))
    with patch('requests.post', return_value=reply), pytest.raises(ValueError, match='firma del lote'):
        ManagerSigner('http://manager', 'token').sign(batch, 'ab' * 32, ZERO_ACCOUNT)


def test_signature_travels_publisher_manager_verifier(verifier):
    sys.path.insert(0, str(ROOT / 'apps/manager'))
    sys.path.insert(0, str(ROOT / 'apps/publisher'))
    from publisher_support.signer import ManagerSigner
    from verifier_support.poseidon import batch_commitment

    readings = [100 + i for i in range(32)]
    keys = verify_batch(verifier, readings)
    batch = {'sessionId': 9, 'salt': '5', 'eventKeys': keys,
             'verifierId': verifier.verifier_id, 'managerId': 'manager-default', 'readerId': 'reader'}
    commitment = f'{batch_commitment(readings, 5, 9):064x}'
    with patch.dict(os.environ, ENV):
        manager = load('manager_chain_test', 'apps/manager/manager.py')
        manager.manager_config.manager_id = 'manager-default'
        try:
            manager.manager_config.verifier_url_list = ['http://verifier:5000']

            def route(url, json=None, **kwargs):
                """requests.post hacia el Manager o el Verifier, atendido por sus apps de Flask."""
                app = manager.app if url.startswith('http://manager') else verifier.app
                response = app.test_client().post('/' + url.rsplit('/', 1)[1], json=json)
                return MagicMock(ok=response.status_code < 400, status_code=response.status_code,
                                 text=response.get_data(as_text=True), json=response.get_json)

            metadata = MagicMock(json=MagicMock(return_value={'verifierId': verifier.verifier_id}))
            with patch('requests.post', side_effect=route), patch('requests.get', return_value=metadata):
                signature = ManagerSigner('http://manager:3003', 'manager').sign(batch, commitment, ZERO_ACCOUNT)
                bad = dict(batch, eventKeys=keys[:31] + [str(uuid.uuid4())])
                with pytest.raises(RuntimeError, match='422'):
                    ManagerSigner('http://manager:3003', 'manager').sign(bad, commitment, ZERO_ACCOUNT)
            message = bytes.fromhex(commitment) + (9).to_bytes(32, 'big') + bytes(32) + bytes.fromhex(verifier.verifier_id)
            verifier.public_key.verify(bytes.fromhex(signature), message)
        finally:
            manager.core.close()
