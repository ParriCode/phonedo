"""Real subprocesses, HTTP/SSE sockets, ed25519 validation and isolated LevelDB."""
import base64
import copy
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

import pytest
import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_for(check, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            result = check()
            if result:
                return result
        except requests.RequestException:
            pass
        time.sleep(.1)
    raise AssertionError('Timed out waiting for service/result')


class Subscription:
    def __init__(self, url, token):
        self.response = requests.get(url, headers={'Authorization': 'Bearer ' + token},
                                     stream=True, timeout=(3, 20))
        self.response.raise_for_status()
        self.events = queue.Queue()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()
        assert self.ready.wait(5), 'SSE handshake missing'

    def read(self):
        try:
            for line in self.response.iter_lines(chunk_size=1):
                if line.startswith(b': connected'):
                    self.ready.set()
                if line.startswith(b'data: '):
                    self.events.put(json.loads(line[6:]))
        except (requests.RequestException, ValueError, AttributeError):
            pass

    def next(self):
        return self.events.get(timeout=15)


def test_real_pipeline(tmp_path):
    ports = {name: port() for name in ('reader', 'manager', 'verifier', 'storage')}
    urls = {name: f'http://127.0.0.1:{value}' for name, value in ports.items()}
    config = tmp_path / 'manager.json'
    config.write_text(json.dumps({'subscriptions': {'readers': [urls['reader']]}, 'services': {'verifiers': [urls['verifier']], 'storages': [urls['storage']]},
                                 'stream': {'enabled': True}, 'outputStreams': {'verifiers': True}}))
    signing_key = Ed25519PrivateKey.generate()
    key_file = tmp_path / 'signing_key.json'
    key_file.write_text(json.dumps({'kty': 'OKP', 'crv': 'Ed25519',
                                    'd': base64.urlsafe_b64encode(signing_key.private_bytes_raw()).decode().rstrip('=')}))
    verifier_config = tmp_path / 'verifier.json'
    verifier_config.write_text(json.dumps({'keyPath': str(key_file), 'server': {'publicUrl': urls['verifier']},
                                         'subscriptions': {'managers': [urls['manager']]}}))
    env = {**os.environ, 'VERIFIER_CONFIG_PATH': str(verifier_config), 'MANAGER_PASSWORD': 'integration-only', 'API_TOKEN_MANAGER': 'manager-test',
           'API_TOKEN_STORAGE': 'storage-test', 'API_TOKEN_VERIFIER': 'verifier-test',
           'API_TOKEN_READER': '', 'MANAGER_CONFIG_PATH': str(config),
           'PHONENDO_DB_PATH': str(tmp_path / 'db'), 'PHONENDO_LOGS_DIR': str(tmp_path / 'logs'),
           'PHONENDO_LOGGING': 'false', 'PHONENDO_VERBOSE': 'false', 'PHONENDO_DEV': 'false',
           'MANAGER_HTTP_TIMEOUT_SECONDS': '2',
           }
    env.update({'PORT_' + name.upper(): str(value) for name, value in ports.items()})
    processes, logs = [], []
    def start(name, args):
        log = (tmp_path / (name + '.log')).open('w')
        logs.append(log)
        process = subprocess.Popen([sys.executable, *args], cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT)
        processes.append(process)
        return process
    try:
        start('storage', ['apps/storage/main.py'])
        start('manager', ['apps/manager/manager.py'])
        start('verifier', ['apps/verifier/verifier.py'])
        for name in ('storage', 'manager', 'verifier'):
            wait_for(lambda name=name: requests.get(urls[name] + '/', timeout=1).status_code == 200)
        # General monitoring stream; the actual Verifier uses HTTP exclusively.
        captured = Subscription(urls['manager'] + '/stream', 'manager-test')
        redundant = requests.get(urls['manager'] + '/stream/verifier', headers={
            'Authorization':'Bearer verifier-test', 'X-Phonendo-Service-URL':urls['verifier']}, timeout=3)
        assert redundant.status_code == 409
        verified_a = Subscription(urls['verifier'] + '/stream', 'verifier-test')
        verified_b = Subscription(urls['verifier'] + '/stream', 'verifier-test')
        # Real ReaderCore + ReaderServer, emit the same Linux example on an isolated port.
        code = f'''import sys, asyncio
sys.path[:0] = ['apps/reader', 'apps/reader/python/core', 'apps/reader/python/server']
from examples.linux import main
from reader_server import ReaderServer, ServerConfig
main.ReaderServer = lambda core, config: ReaderServer(core, ServerConfig(enabled=True, port={ports['reader']}))
asyncio.run(main.main())
'''
        reader = start('reader', ['-c', code])
        original = captured.next()
        first, second = verified_a.next(), verified_b.next()
        assert first == second
        def stored_event():
            records = requests.get(urls['storage'] + '/raw', timeout=2).json()
            return next(({'key': key, 'value': value} for key, value in records.items()
                         if value.get('status') == 'Verified' and value.get('payload') == original['value']['payload']), None)
        persisted = wait_for(stored_event)
        stored = persisted['value']
        # Verify the HTTP result and its persisted copy.
        public_key = signing_key.public_key()
        def check_signature(message):
            unsigned = copy.deepcopy(message)
            signature = bytes.fromhex(unsigned['value'].pop('verifierSign'))
            encoded = json.dumps(unsigned, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
            public_key.verify(signature, encoded)
        check_signature(first)
        check_signature(persisted)
        assert stored['payload'] == original['value']['payload']
        assert stored['status'] == 'Verified'
        for field in ('readerId', 'deviceId', 'payloadFormat', 'creationDatetime'):
            assert stored[field] == original['value'][field]
        altered = copy.deepcopy(first)
        altered['value']['payload']['simple_result'] = -999
        with pytest.raises(InvalidSignature):
            check_signature(altered)
        for field in ('payload', 'readerId', 'deviceId', 'creationDatetime'):
            altered = copy.deepcopy(original)
            altered['value'][field] = {'changed': True} if field == 'payload' else 1 if field == 'creationDatetime' else 'changed'
            response = requests.post(urls['verifier'] + '/verify',
                                     json={'token': 'verifier-test', 'message': altered}, timeout=5)
            assert response.status_code == 422, response.text
        assert requests.get(urls['storage'] + '/raw', timeout=2).json()[persisted['key']] == stored
        reader.terminate()
        reader.wait(timeout=5)
        # Prove the Verifier consumes the Manager SSE, independently of POST /verify:
        manager = processes[1]
        manager.terminate()
        manager.wait(timeout=5)
        settings = json.loads(config.read_text())
        settings['services']['verifiers'] = []
        settings['stream']['enabled'] = False
        settings['subscriptions']['verifiers'] = [urls['verifier']]
        settings['subscriptions']['storages'] = [urls['storage']]
        config.write_text(json.dumps(settings))
        start('manager-sse-only', ['apps/manager/manager.py'])
        wait_for(lambda: requests.get(urls['manager'] + '/', timeout=1).status_code == 200)
        # Reconnection delay is 5 seconds; emit until the consumer has reconnected.
        end = time.monotonic() + 15
        found = False
        while time.monotonic() < end and not found:
            body = {'token': 'manager-test', 'readerId': 'http-test', 'deviceId': 'simulated-device',
                    'eventType': 'observation', 'payloadFormat': 'application/json', 'payload': {'sseOnly': True}}
            reply = requests.post(urls['manager'] + '/newEvent', json=body, timeout=5)
            assert reply.status_code == 200
            time.sleep(.5)
            while not verified_a.events.empty():
                event = verified_a.events.get_nowait()
                if event.get('value', {}).get('payload') == {'sseOnly': True}:
                    check_signature(event)
                    found = True
        assert found, 'Verifier never consumed the real Manager SSE'
        wait_for(lambda: any(v.get('payload') == {'sseOnly':True} and v.get('status') == 'Verified'
            for v in requests.get(urls['storage']+'/raw',timeout=2).json().values()))
    finally:
        for process in reversed(processes):
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
