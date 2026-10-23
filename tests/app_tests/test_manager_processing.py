import copy
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'libs'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'MANAGER_PASSWORD': 'test-only-secret',
            'API_TOKEN_MANAGER': 'test', 'API_TOKEN_VERIFIER': 'verify',
            'PHONENDO_LOGGING': 'false', 'PHONENDO_VERBOSE': 'false'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.manager = load('manager_test', 'apps/manager/manager.py')
        self.verifier = load('verifier_test', 'apps/verifier/verifier.py')
        self.body = dict(token='test', deviceId='device', readerId='reader',
                         payload={'temperature': 25}, payloadFormat='application/json', eventType='observation')
        self.captured = None

    def exchange(self, url, body):
        message = copy.deepcopy(body['message'])
        if body['token'] == 'verify':
            self.captured = message
            response = self.verifier.app.test_client().post('/verify', json=body)
            self.assertEqual(response.status_code, 200)
            return response.get_json()
        return message

    def request(self, exchange=None):
        send = exchange or self.exchange
        client = self.manager.manager_client
        with patch.object(client, 'get_device', return_value={}), \
             patch.object(client, 'verify_event', side_effect=lambda message: send('verifier', {'token': 'verify', 'message': message})), \
             patch.object(client, 'store_event', side_effect=lambda message: send('storage', {'token': 'storage', 'message': message})):
            return self.manager.app.test_client().post('/newEvent', json=self.body)

    def test_success_and_payload_tampering(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'Verified')
        self.assertTrue(self.verifier.verify_event(self.captured))
        for field, value in [('payload', {'temperature': 99}), ('readerId', 'other'), ('deviceId', 'other'), ('creationDatetime', 1)]:
            forged = copy.deepcopy(self.captured)
            forged['value'][field] = value
            self.assertFalse(self.verifier.verify_event(forged))
        forged = copy.deepcopy(self.captured)
        forged['value']['payload']['temperature'] = 99
        result = self.verifier.app.test_client().post('/verify', json={'token':'verify','message':forged})
        self.assertEqual(result.status_code, 422)
        with patch.dict(os.environ, {'MANAGER_PASSWORD': 'different'}):
            self.assertFalse(self.verifier.verify_event(self.captured))

    def test_explicit_rejection_discards_without_storage_write(self):
        calls = []
        def exchange(url, body):
            calls.append(body)
            if body['token'] == 'verify':
                raise __import__("client").InternalPostError('verifier', 422, 'rejected')
            raise AssertionError('Rejected data reached Storage')
        response = self.request(exchange)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json['status'], 'Rejected')
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.manager.core.pending_events), 0)

    def test_timeout_queues_then_retries_without_resigning(self):
        calls = 0
        def exchange(url, body):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise __import__("requests").Timeout()
            return self.exchange(url, body)
        response = self.request(exchange)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json['status'], 'Pending')
        self.assertEqual(len(self.manager.core.pending_events), 1)
        client = self.manager.manager_client
        with patch.object(client, 'verify_event', side_effect=lambda message: exchange('verifier', {'token': 'verify', 'message': message})), \
             patch.object(client, 'store_event', side_effect=lambda message: exchange('storage', {'token': 'storage', 'message': message})):
            self.manager.core.pending_events.retry_once()
        self.assertEqual(len(self.manager.core.pending_events), 0)
        self.assertEqual(calls, 3)
        self.manager.core.pending_events.close()

    def test_storage_timeout_resumes_at_verified_stage(self):
        calls = 0
        def exchange(url, body):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise __import__("requests").Timeout()
            return self.exchange(url, body)
        response = self.request(exchange)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json['stage'], 'store_verified')
        client = self.manager.manager_client
        with patch.object(client, 'verify_event', side_effect=lambda message: exchange('verifier', {'token': 'verify', 'message': message})), \
             patch.object(client, 'store_event', side_effect=lambda message: exchange('storage', {'token': 'storage', 'message': message})):
            self.manager.core.pending_events.retry_once()
        self.assertEqual(calls, 3)
        self.assertEqual(len(self.manager.core.pending_events), 0)
        self.manager.core.pending_events.close()

    def test_queue_discards_oldest_when_full(self):
        from pending_events import PendingEvents
        dropped = []
        queue = PendingEvents(2, 1, lambda job: False, lambda job: dropped.append(job['message']['key']))
        for key in ('a','b','c'):
            queue.put({'message': {'key': key}}, start=False)
        self.assertEqual(dropped, ['a'])
        self.assertEqual(len(queue), 2)
        queue.close()

    def test_missing_secret_not_accepted(self):
        with patch.dict(os.environ, {'MANAGER_PASSWORD': ''}):
            self.assertEqual(self.request().status_code, 500)

if __name__ == '__main__':
    unittest.main()
