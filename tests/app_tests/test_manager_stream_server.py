import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('manager_stream_server', ROOT / 'apps/manager/server.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StreamServerTests(unittest.TestCase):
    def config(self, **flags):
        values = dict(stream=True, stream_verifiers=True, stream_storages=True,
                      api_token_verifier='verifier-secret', api_token_storage='storage-secret')
        values.update(flags)
        return SimpleNamespace(**values)

    def test_conditional_routes(self):
        for flags, expected in [({'stream': False}, []),
                                ({'stream_verifiers': False}, ['/stream/storage']),
                                ({'stream_storages': False}, ['/stream/verifier'])]:
            app = Flask(__name__)
            MODULE.ManagerServer(app, self.config(**flags))
            routes = {rule.rule for rule in app.url_map.iter_rules()}
            self.assertEqual(routes & {'/stream/verifier', '/stream/storage'}, set(expected))

    def test_auth_and_isolated_stream_delivery(self):
        app = Flask(__name__)
        server = MODULE.ManagerServer(app, self.config())
        client = app.test_client()
        self.assertEqual(client.get('/stream/verifier').status_code, 401)
        self.assertEqual(client.get('/stream/verifier', headers={'Authorization':'Bearer storage-secret'}).status_code, 401)
        verifier = client.get('/stream/verifier', headers={'Authorization':'Bearer verifier-secret'}, buffered=False)
        storage = client.get('/stream/storage', headers={'Authorization':'Bearer storage-secret'}, buffered=False)
        self.assertIn(b'connected', next(verifier.response))
        self.assertIn(b'connected', next(storage.response))
        server.publish_captured({'key':'captured-1','value':{'status':'Captured'}})
        server.publish_verified({'key':'verified-1','value':{'status':'Verified'}})
        first = next(verifier.response)
        second = next(storage.response)
        self.assertIn(b'captured-1', first)
        self.assertNotIn(b'verified-1', first)
        self.assertIn(b'verified-1', second)
        self.assertNotIn(b'captured-1', second)
        verifier.close()
        storage.close()

    def test_slow_subscriber_is_closed_without_affecting_others(self):
        stream = MODULE.EventStream(queue_size=1)
        with stream.subscribe() as slow, stream.subscribe() as fast:
            stream.publish({'key':'1'})
            self.assertEqual(fast.get_nowait()['key'], '1')
            stream.publish({'key':'2'})
            self.assertIsNone(slow.get_nowait())
            self.assertEqual(fast.get_nowait()['key'], '2')

if __name__ == '__main__':
    unittest.main()
