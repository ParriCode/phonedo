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
    body = {'token': 'verify', 'sessionId': 7, 'salt': '123', 'patient': ZERO_ACCOUNT, 'eventKeys': keys}
    with patch.dict(os.environ, ENV):
        response = verifier.app.test_client().post('/signBatch', json=body)
    assert response.status_code == 200
    reply = response.get_json()
    assert reply['commitment'] == f'{batch_commitment(readings, 123, 7):064x}'
    message = bytes.fromhex(reply['commitment']) + (7).to_bytes(32, 'big') + bytes(32)
    verifier.public_key.verify(bytes.fromhex(reply['signature']), message)


def test_event_and_batch_signatures_share_one_ed25519_key(verifier):
    result, status = verifier.verify_message(captured(verifier, 100))
    assert status == 200
    message = result['message']
    signature = bytes.fromhex(message['value'].pop('verifierSign'))
    verifier.public_key.verify(signature, verifier.canonical_json(message).encode())


def test_verifier_rejects_unknown_events_and_bad_token(verifier):
    keys = verify_batch(verifier, [100] * 31) + [str(uuid.uuid4())]
    body = {'token': 'verify', 'sessionId': 7, 'salt': '1', 'patient': ZERO_ACCOUNT, 'eventKeys': keys}
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
            reply = {'commitment': 'ab' * 32, 'signature': 'cd' * 64}
            body = {'sessionId': 7, 'salt': '1', 'patient': ZERO_ACCOUNT, 'eventKeys': ['k']}
            with patch.object(manager.manager_client, '_post', return_value=reply) as post:
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
    batch = {'sessionId': 7, 'salt': '1', 'eventKeys': ['k']}
    reply = MagicMock(ok=True, json=MagicMock(return_value={'commitment': 'ab' * 32, 'signature': 'cd' * 64}))
    with patch('requests.post', return_value=reply) as post:
        assert signer.sign(batch, 'ab' * 32, ZERO_ACCOUNT) == 'cd' * 64
        with pytest.raises(ValueError, match='no coincide'):
            signer.sign(batch, 'ef' * 32, ZERO_ACCOUNT)
    assert post.call_args.args == ('http://manager:3003/signBatch',)
    assert post.call_args.kwargs['json'] == {'token': 'manager', 'sessionId': 7, 'salt': '1',
                                             'patient': ZERO_ACCOUNT, 'eventKeys': ['k']}


def test_account_key_checks_the_strkey():
    sys.path.insert(0, str(ROOT / 'apps/verifier'))
    from verifier_support.batch_signer import account_key

    assert account_key(ZERO_ACCOUNT) == bytes(32)
    with pytest.raises(ValueError):
        account_key(ZERO_ACCOUNT[:-1] + 'G')


def test_signature_travels_publisher_manager_verifier(verifier):
    sys.path.insert(0, str(ROOT / 'apps/manager'))
    sys.path.insert(0, str(ROOT / 'apps/publisher'))
    from publisher_support.signer import ManagerSigner
    from verifier_support.poseidon import batch_commitment

    readings = [100 + i for i in range(32)]
    keys = verify_batch(verifier, readings)
    batch = {'sessionId': 9, 'salt': '5', 'eventKeys': keys}
    commitment = f'{batch_commitment(readings, 5, 9):064x}'
    with patch.dict(os.environ, ENV):
        manager = load('manager_chain_test', 'apps/manager/manager.py')
        try:
            manager.manager_config.verifier_url_list = ['http://verifier:5000']

            def route(url, json=None, **kwargs):
                """requests.post hacia el Manager o el Verifier, atendido por sus apps de Flask."""
                app = manager.app if url.startswith('http://manager') else verifier.app
                response = app.test_client().post('/' + url.rsplit('/', 1)[1], json=json)
                return MagicMock(ok=response.status_code < 400, status_code=response.status_code,
                                 text=response.get_data(as_text=True), json=response.get_json)

            with patch('requests.post', side_effect=route):
                signature = ManagerSigner('http://manager:3003', 'manager').sign(batch, commitment, ZERO_ACCOUNT)
                bad = dict(batch, eventKeys=keys[:31] + [str(uuid.uuid4())])
                with pytest.raises(RuntimeError, match='422'):
                    ManagerSigner('http://manager:3003', 'manager').sign(bad, commitment, ZERO_ACCOUNT)
            message = bytes.fromhex(commitment) + (9).to_bytes(32, 'big') + bytes(32)
            verifier.public_key.verify(bytes.fromhex(signature), message)
        finally:
            manager.core.close()
