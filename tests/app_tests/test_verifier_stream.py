import importlib.util
import os
from pathlib import Path
from unittest.mock import patch


def test_verified_results_fan_out_and_rejections_are_not_published():
    root = Path(__file__).resolve().parents[2]
    with patch.dict(os.environ, {'API_TOKEN_VERIFIER': 'stream-test', 'VERIFIER_MANAGER_STREAMS': '[]'}):
        spec = importlib.util.spec_from_file_location('verifier_stream_test', root / 'apps/verifier/verifier.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        assert verifier.app.test_client().get('/stream').status_code == 401
        headers = {'Authorization': 'Bearer stream-test'}
        first = verifier.app.test_client().get('/stream', headers=headers, buffered=False)
        second = verifier.app.test_client().get('/stream', headers=headers, buffered=False)
        a, b = iter(first.response), iter(second.response)
        assert b'connected' in next(a)
        assert b'connected' in next(b)
        message = {'key': 'event-id', 'value': {'status': 'Verified'}}
        with patch.object(verifier, 'verify_message', return_value=({'verified': True, 'message': message}, 200)):
            verifier.consume_manager_event({'key': 'event-id'})
        assert b'event-id' in next(a)
        assert b'event-id' in next(b)
        with patch.object(verifier, 'verify_message', return_value=({'verified': False}, 422)), patch.object(verifier.verification_stream, 'publish') as publish:
            verifier.consume_manager_event({})
            publish.assert_not_called()
        first.close()
        second.close()
        verifier.manager_streams.close()
