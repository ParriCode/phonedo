"""Dos Verifiers con claves ed25519 distintas y varios Publishers sobre un mismo Manager.

Procesos reales por HTTP/SSE y pruebas Groth16 reales. Solo la Stellar CLI es un doble:
hace de contrato `adherence` (firma del Verifier de ese contrato y anti-replay) y anota
cada pago en un libro. Todos los Publishers pagan con la misma cartera `phonendo`.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test_pipeline import port, wait_for

ROOT = Path(__file__).resolve().parents[2]
PATIENT = 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF'
CONTRACTS = {'a': 'CVERIFIERA', 'b': 'CVERIFIERB'}

pytestmark = pytest.mark.skipif(
    shutil.which('node') is None or not (ROOT / 'circuits/build/range_adherence.zkey').is_file()
    or not (ROOT / 'circuits/node_modules').is_dir(),
    reason='requiere Node.js y circuits/build (npm install && npm run setup en circuits/)')

# Contrato simulado: misma comprobación de firma y anti-replay que claim() en Soroban.
FAKE_STELLAR = r'''#!/usr/bin/env python3
import base64, fcntl, hashlib, json, os, sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

args = sys.argv[1:]
value = lambda flag: args[args.index(flag) + 1]
contract, source = value('--id'), value('--source')
if not (Path(value('--config-dir')) / 'identity' / (source + '.toml')).is_file():
    sys.exit('error: identidad %s no encontrada' % source)
session = int(value('--session_id'))
patient = base64.b32decode(value('--patient'))[1:33]
message = bytes.fromhex(value('--commitment')) + session.to_bytes(32, 'big') + patient
verifier = bytes.fromhex(json.loads(os.environ['FAKE_CONTRACTS'])[contract])
try:
    Ed25519PublicKey.from_public_bytes(verifier).verify(bytes.fromhex(value('--signature')), message + verifier)
except Exception:
    sys.exit('error: ed25519 signature verification failed')
with open(os.environ['FAKE_LEDGER'], 'a+') as ledger:
    fcntl.flock(ledger, fcntl.LOCK_EX)
    ledger.seek(0)
    paid = [json.loads(line) for line in ledger if line.strip()]
    if any(item['contract'] == contract and item['session'] == session for item in paid):
        sys.exit('error: HostError: Error(Contract, #1)')
    ledger.write(json.dumps({'contract': contract, 'session': session, 'source': source}) + '\n')
print('https://stellar.expert/explorer/testnet/tx/' + hashlib.sha256(b'%s:%d' % (contract.encode(), session)).hexdigest())
'''


def key_file(path):
    key = Ed25519PrivateKey.generate()
    path.write_text(json.dumps({'kty': 'OKP', 'crv': 'Ed25519',
                                'd': base64.urlsafe_b64encode(key.private_bytes_raw()).decode().rstrip('=')}))
    return key.public_key().public_bytes_raw().hex()


def test_two_verifiers_sign_and_each_publisher_pays_only_its_own(tmp_path):
    names = ['storage', 'manager', 'verifier-a', 'verifier-b', 'publisher-a', 'publisher-b', 'publisher-a2']
    ports = {name: port() for name in names}
    urls = {name: f'http://127.0.0.1:{ports[name]}' for name in names}
    verifier_ids = {name: key_file(tmp_path / f'{name}.json') for name in ('a', 'b')}
    assert verifier_ids['a'] != verifier_ids['b']

    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    (bin_dir / 'stellar').write_text(FAKE_STELLAR.replace('python3', sys.executable, 1))
    (bin_dir / 'stellar').chmod(0o755)
    wallets = tmp_path / 'keys/stellar'
    (wallets / 'identity').mkdir(parents=True)
    (wallets / 'identity/phonendo.toml').write_text('secret_key = "no se usa con el doble"\n')
    ledger = tmp_path / 'ledger.jsonl'
    ledger.touch()

    processes, logs = [], []
    base_env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}',
                'FAKE_LEDGER': str(ledger),
                'FAKE_CONTRACTS': json.dumps({CONTRACTS[name]: verifier_ids[name] for name in CONTRACTS}),
                'MANAGER_PASSWORD': 'two-verifiers', 'API_TOKEN_MANAGER': 'm-token',
                'API_TOKEN_VERIFIER': 'v-token', 'API_TOKEN_STORAGE': 's-token',
                'PHONENDO_LOGGING': 'false', 'PHONENDO_VERBOSE': 'false', 'PHONENDO_DEV': 'false',
                'PHONENDO_LOGS_DIR': str(tmp_path / 'logs')}

    def start(name, service, entry, config):
        config.setdefault('server', {})['publicUrl'] = urls[name]
        path = tmp_path / (name + '.config.json')
        path.write_text(json.dumps(config))
        env = {**base_env, service.upper() + '_CONFIG_PATH': str(path), 'PORT_' + service.upper(): str(ports[name]),
               'PHONENDO_DB_PATH': str(tmp_path / (name + '.db'))}
        log = (tmp_path / (name + '.log')).open('w')
        logs.append(log)
        processes.append(subprocess.Popen([sys.executable, str(ROOT / 'apps' / service / entry)],
                                          env=env, cwd=tmp_path, stdout=log, stderr=subprocess.STDOUT))
        wait_for(lambda: requests.get(urls[name] + '/', timeout=1).status_code == 200)

    def publisher(name, verifier):
        start(name, 'publisher', 'publisher.py', {
            'subscriptions': {'managers': [urls['manager']]}, 'batchSize': 5,
            'contracts': {verifier_ids[verifier]: CONTRACTS[verifier]},
            'policy': {'minValue': 90, 'maxValue': 130, 'minCount': 4}, 'patients': {'default': PATIENT},
            'circuitsPath': str(ROOT / 'circuits'),
            'stellar': {'source': 'phonendo', 'network': 'testnet', 'configDir': str(wallets)}})

    def public_logs(name):
        return [json.loads(line) for line in requests.get(urls[name] + '/logs', timeout=2).json()]

    try:
        start('storage', 'storage', 'main.py', {'subscriptions': {'managers': [urls['manager']]}})
        for name in ('a', 'b'):
            start('verifier-' + name, 'verifier', 'verifier.py', {'keyPath': str(tmp_path / f'{name}.json')})
        start('manager', 'manager', 'manager.py', {
            'managerId': 'manager-shared',
            'services': {'verifiers': [urls['verifier-a'], urls['verifier-b']], 'storages': [urls['storage']]},
            'stream': {'enabled': True}, 'outputStreams': {'verifiers': True, 'storages': True}})
        # publisher-a2 sirve al mismo Verifier que publisher-a: intentará cobrar las mismas sesiones.
        for name, verifier in (('publisher-a', 'a'), ('publisher-b', 'b'), ('publisher-a2', 'a')):
            publisher(name, verifier)
        for name in ('publisher-a', 'publisher-b', 'publisher-a2'):
            wait_for(lambda: {'peer': urls['manager'], 'transport': 'sse'} in requests.get(urls[name] + '/info', timeout=1).json())

        for index in range(5):
            reply = requests.post(urls['manager'] + '/newEvent', timeout=8, json={
                'token': 'm-token', 'readerId': 'reader-shared', 'deviceId': 'pulse-band',
                'eventType': 'observation', 'payloadFormat': 'application/json',
                'payload': {'simple_result': 95 + index % 30}})
            assert reply.status_code == 207, reply.text
            assert [item['httpStatus'] for item in reply.json()['results']] == [200, 200]

        def paid():
            entries = [json.loads(line) for line in ledger.read_text().splitlines()]
            return entries if {entry['contract'] for entry in entries} == set(CONTRACTS.values()) else None
        entries = wait_for(paid, seconds=60)
        # Cada contrato cobra una sola sesión, firmada por su Verifier y pagada con la cartera phonendo.
        assert sorted(entry['contract'] for entry in entries) == sorted(CONTRACTS.values())
        assert {entry['source'] for entry in entries} == {'phonendo'}
        assert entries[0]['session'] != entries[1]['session']

        # El segundo Publisher del Verifier A llega a la misma sesión y el contrato la rechaza.
        def replay_rejected():
            events = public_logs('publisher-a') + public_logs('publisher-a2')
            return [event for event in events if event['message'] == 'publisher_session_failed']
        failed = wait_for(replay_rejected, seconds=60)
        assert all('ya cobrada' in event['error'] for event in failed)
        assert len([json.loads(line) for line in ledger.read_text().splitlines()]) == 2
        # Ningún Publisher procesa lotes de un Verifier que no sirve.
        assert not any(event['message'] == 'publisher_session_failed' for event in public_logs('publisher-b'))
        paid_by = {event.get('verifierId') for name in ('publisher-a', 'publisher-a2', 'publisher-b')
                   for event in public_logs(name) if event['message'] == 'publisher_session_paid'}
        assert paid_by == set(verifier_ids.values())
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()
