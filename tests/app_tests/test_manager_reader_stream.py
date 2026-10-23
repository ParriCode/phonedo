import importlib.util
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'libs'))
sys.path.insert(0, str(ROOT / 'apps/manager'))


class Response:
    def __init__(self, payload=None, lines=()):
        self.payload = payload
        self.lines = lines

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload

    def iter_lines(self, decode_unicode=False):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class ReaderStreamTests(unittest.TestCase):
    def test_sse_metadata_identity_and_observation(self):
        from client import ManagerClient
        config = type('Config', (), {'api_token_reader': 'reader-secret'})()
        client = ManagerClient(config)
        calls = []
        event = b'{"eventType":"observation","readerId":"r1","deviceId":"d1","payloadFormat":"application/json","payload":{"value":1}}'
        responses = [Response({'readerId': 'r1', 'capabilities': {'stream': True}}),
                     Response(lines=[b': connected', b'', b'event: observation', b'data: ' + event, b''])]
        with patch('client.requests.get', side_effect=responses) as get:
            client.consume_reader_stream('http://reader/', calls.append, threading.Event())
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['readerId'], 'r1')
        self.assertEqual(get.call_args_list[0].args[0], 'http://reader/metadata')
        self.assertEqual(get.call_args_list[1].args[0], 'http://reader/stream')
        self.assertEqual(get.call_args_list[1].kwargs['headers']['Authorization'], 'Bearer reader-secret')

    def test_http_reader_takes_priority_over_stream(self):
        with patch.dict(os.environ, {'MANAGER_PASSWORD': 'test-secret',
                                      'API_TOKEN_MANAGER': 'manager-token',
                                      'PHONENDO_LOGGING': 'false'}):
            spec = importlib.util.spec_from_file_location('manager_stream_priority',
                                                           ROOT / 'apps/manager/manager.py')
            manager = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(manager)
            body = {'token': 'manager-token', 'eventType': 'observation',
                    'readerId': 'r1', 'deviceId': 'd1', 'payloadFormat': 'application/json',
                    'payload': {'value': 1}}
            with patch.object(manager.core, 'attempt_event', return_value=({'status': 'Verified'}, 200)) as process:
                manager.core.on_reader_stream_event({key: value for key, value in body.items() if key != 'token'})
                self.assertEqual(process.call_count, 1)
                response = manager.app.test_client().post('/newEvent', json=body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(process.call_count, 2)
                manager.core.on_reader_stream_event({key: value for key, value in body.items() if key != 'token'})
                self.assertEqual(process.call_count, 2)
            manager.core.pending_events.close()


if __name__ == '__main__':
    unittest.main()
