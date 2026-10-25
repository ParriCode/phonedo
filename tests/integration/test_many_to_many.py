"""Two Managers, two Verifiers and two Storages over real HTTP/SSE."""
import json
import os
from pathlib import Path
import subprocess
import sys

import requests

from test_pipeline import port, wait_for

ROOT = Path(__file__).resolve().parents[2]


def test_many_to_many_http_and_storage_streams(tmp_path):
    names = ['m1', 'm2', 'v1', 'v2', 's1', 's2']
    ports = {name: port() for name in names}
    urls = {name: f'http://127.0.0.1:{ports[name]}' for name in names}
    processes, logs = [], []
    def start(name, service, entry, config):
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(config))
        env = {**os.environ, service.upper() + '_CONFIG_PATH': str(path),
               'PORT_' + service.upper(): str(ports[name]), 'MANAGER_PASSWORD': 'nn-secret',
               'API_TOKEN_MANAGER': 'm-token', 'API_TOKEN_VERIFIER': 'v-token',
               'API_TOKEN_STORAGE': 's-token', 'PHONENDO_DB_PATH': str(tmp_path / (name + '.db')),
               'PHONENDO_LOGGING': 'false', 'PHONENDO_VERBOSE': 'false', 'PHONENDO_DEV': 'false',
               'PHONENDO_LOGS_DIR': str(tmp_path / 'logs')}
        log = (tmp_path / (name + '.log')).open('w')
        logs.append(log)
        processes.append(subprocess.Popen([sys.executable, str(ROOT / 'apps' / service / entry)],
            env=env, cwd=tmp_path, stdout=log, stderr=subprocess.STDOUT))
        wait_for(lambda: requests.get(urls[name] + '/', timeout=1).status_code == 200)
    try:
        for name in ['s1','s2']:
            start(name, 'storage', 'main.py', {'subscriptions': {'managers':[urls['m1'],urls['m2']]},
                                              'stream':{'enabled':name != 's1'}})
        for name in ['m1','m2']:
            start(name, 'manager', 'manager.py', {'services': {
                'storages':[urls['s1'],urls['s2']] if name=='m1' else [urls['s2']],
                'verifiers':[urls['v1'],urls['v2']]},
                'stream':{'enabled':name != 'm1'}, 'outputStreams':{'storages':True,'verifiers':True}})
        for name in ['v1','v2']:
            start(name, 'verifier', 'verifier.py', {'subscriptions':{'managers':[urls['m1'],urls['m2']]}})
        results = []
        for name in ['m1','m2']:
            # Wait for the real Storage SSE subscribers by observing a probe.
            # Repeat delivery until the SSE-only storage has received an event.
            def emit_and_check():
                reply = requests.post(urls[name]+'/newEvent', json={'token':'m-token',
                    'readerId':name,'deviceId':name+'-device','eventType':'observation',
                    'payloadFormat':'application/json','payload':{'source':name}},timeout=8)
                assert reply.status_code == 207, reply.text
                relations = reply.json()['results']
                assert len(relations) == 2
                assert all(item['httpStatus'] == 200 for item in relations)
                results.extend(item['result']['eventId'] for item in relations)
                return any(v.get('payload') == {'source':name} for v in
                           requests.get(urls['s1']+'/raw',timeout=2).json().values())
            wait_for(emit_and_check, seconds=20)
        def all_sources_present():
            for storage in ['s1','s2']:
                records = requests.get(urls[storage]+'/raw',timeout=2).json()
                for manager in ['m1','m2']:
                    matching = [v for v in records.values() if v.get('payload')=={'source':manager}]
                    if len(matching) < 2:
                        return False
                    assert all(v['status']=='Verified' and v['verifierSign'] for v in matching)
            return True
        wait_for(all_sources_present, seconds=20)
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
