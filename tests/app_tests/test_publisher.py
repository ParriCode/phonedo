"""Publisher: lotes de lecturas Verified del Manager, firma del lote y claim()."""
import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/publisher'))
ZERO_ACCOUNT = 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF'


@pytest.fixture
def publisher(tmp_path, monkeypatch):
    config = tmp_path / 'publisher.json'
    config.write_text(json.dumps({
        'batchSize': 4,
        'contracts': {'verifier-a': 'CCONTRACT'},
        'policy': {'minValue': 90, 'maxValue': 130, 'minCount': 3},
        'patients': {'default': ZERO_ACCOUNT},
        'stellar': {'contractId': 'CCONTRACT', 'source': 'alex'},
    }))
    monkeypatch.setenv('PUBLISHER_CONFIG_PATH', str(config))
    monkeypatch.setenv('PHONENDO_LOGS_DIR', str(tmp_path / 'logs'))
    monkeypatch.setenv('PHONENDO_LOGGING', 'false')
    spec = importlib.util.spec_from_file_location('publisher_under_test', ROOT / 'apps/publisher/publisher.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    module.manager_subscriptions.close()


def verified(device_id, result, created=1000, key=None):
    return {'key': key or f'{device_id}-{result}', 'value': {
        'status': 'Verified', 'verifierSign': 'sig', 'deviceId': device_id,
        'managerId': 'manager-a', 'verifierId': 'verifier-a', 'readerId': 'reader-a',
        'observationId': key or f'{device_id}-{result}',
        'creationDatetime': created, 'payload': {'simple_result': result}}}


def wait_until(condition):
    for _ in range(100):
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError('timeout')


def test_batches_verified_readings_per_device_once():
    from publisher_support.batcher import SessionBatcher

    batcher = SessionBatcher(2)
    assert batcher.add(verified('a', 101.6, created=5)) is None
    assert batcher.add(verified('a', 101.6, created=5)) is None
    assert batcher.add(verified('b', 300)) is None
    assert batcher.add({'key': 'x', 'value': {'status': 'Captured', 'payload': {'simple_result': 1}}}) is None
    batch = batcher.add(verified('a', -4))
    assert batch['readings'] == [102, 0]
    assert batch['eventKeys'] == ['a-101.6', 'a--4']
    assert batch['startedAt'] == 5
    assert batcher.pending[('manager-a', 'verifier-a', 'reader-a', 'b')]['readings'] == [255]


def test_public_info_and_logs(publisher):
    client = publisher.app.test_client()
    publisher.manager_subscriptions.connected.add('http://manager:3003/stream')
    assert client.get('/info').json == [{'peer': 'http://manager:3003', 'transport': 'sse'}]
    publisher.Logger.info('publisher_connected')
    assert client.get('/logs').json[-1] == 'publisher_connected'


@pytest.mark.parametrize('field', ['managerId', 'verifierId', 'readerId', 'deviceId'])
def test_batches_keep_origins_separate(field):
    from publisher_support.batcher import SessionBatcher
    batcher = SessionBatcher(2)
    first = verified('sensor', 100, key='one')
    second = verified('sensor', 101, key='two')
    second['value'][field] = 'other'
    assert batcher.add(first, 'http://manager-a', 'token-a') is None
    assert batcher.add(second, 'http://manager-b', 'token-b') is None
    third = verified('sensor', 102, key='three')
    batch = batcher.add(third, 'http://manager-a', 'token-a')
    assert batch['eventKeys'] == ['one', 'three']
    assert batch['managerUrl'] == 'http://manager-a'
    assert batch['managerToken'] == 'token-a'


def test_repeated_identity_is_ignored_but_other_manager_is_independent():
    from publisher_support.batcher import SessionBatcher
    batcher = SessionBatcher(2)
    first = verified('sensor', 100, key='one')
    assert batcher.add(first) is None
    repeated = {**first, 'key': 'different-envelope'}
    assert batcher.add(repeated) is None
    other = {**first, 'value': {**first['value'], 'managerId': 'manager-b'}}
    assert batcher.add(other) is None
    assert len(batcher.pending) == 2


def test_full_batch_from_manager_is_proved_signed_and_claimed(publisher):
    publisher.prover.prove = MagicMock(return_value=('ef' * 32, Path('proof.json')))
    publisher.signer = MagicMock(sign=MagicMock(return_value='aa' * 64))
    publisher.claimer.claim = MagicMock(return_value='12' * 32)
    publisher.StellarClaimer = MagicMock(return_value=publisher.claimer)
    for result in (100, 101, 102, 103):
        publisher.consume_manager_event(verified('sensor-1', result, created=42))

    wait_until(lambda: publisher.claimer.claim.called)
    batch, patient, commitment, signature, _ = publisher.claimer.claim.call_args.args
    assert batch['readings'] == [100, 101, 102, 103] and batch['sessionId'] == 42
    assert (patient, commitment, signature) == (ZERO_ACCOUNT, 'ef' * 32, 'aa' * 64)


def test_batch_out_of_range_is_never_claimed(publisher):
    publisher.prover.prove = MagicMock(side_effect=publisher.BatchNotMet('no cumple'))
    publisher.claimer.claim = MagicMock()
    for result in (60, 61, 62, 63):
        publisher.consume_manager_event(verified('sensor-1', result))

    wait_until(lambda: publisher.prover.prove.called)
    time.sleep(0.05)
    publisher.claimer.claim.assert_not_called()


def test_claim_command_and_already_claimed_error():
    from publisher_support.stellar import ClaimFailed, StellarClaimer

    claimer = StellarClaimer('CCONTRACT', 'alex')
    command = claimer.command({'sessionId': 9}, ZERO_ACCOUNT, 'ab', 'cd', Path('p.json'))
    assert command[:9] == ['stellar', 'contract', 'invoke', '--id', 'CCONTRACT', '--source', 'alex',
                           '--network', 'testnet']
    assert command[command.index('--session_id') + 1] == '9'
    done = MagicMock(returncode=0, stdout='', stderr='https://stellar.expert/explorer/testnet/tx/' + 'f' * 64)
    with patch('subprocess.run', return_value=done):
        assert claimer.claim({'sessionId': 9}, ZERO_ACCOUNT, 'ab', 'cd', 'p.json') == 'f' * 64
    failed = MagicMock(returncode=1, stdout='', stderr='error: HostError: Error(Contract, #1)')
    with patch('subprocess.run', return_value=failed), pytest.raises(ClaimFailed, match='ya cobrada'):
        claimer.claim({'sessionId': 9}, ZERO_ACCOUNT, 'ab', 'cd', 'p.json')


def test_claim_reads_utf8_output_of_the_cli(monkeypatch):
    """La CLI imprime emojis en UTF-8; en Windows el decodificador por defecto (cp1252) fallaba."""
    from publisher_support.stellar import StellarClaimer

    claimer = StellarClaimer('CCONTRACT', 'alex')
    script = ("import sys; sys.stdout.buffer.write('\\u2705 https://stellar.expert/explorer/testnet/tx/"
              + 'e' * 64 + "\\n'.encode('utf-8') + bytes([0x8f]))")
    monkeypatch.setattr(claimer, 'command', lambda *args: [sys.executable, '-c', script])
    assert claimer.claim({'sessionId': 9}, ZERO_ACCOUNT, 'ab', 'cd', 'p.json') == 'e' * 64
