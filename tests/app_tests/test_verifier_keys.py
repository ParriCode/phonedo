import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch


def test_verifier_starts_with_temporary_key_when_key_file_is_missing(tmp_path):
    root = Path(__file__).resolve().parents[2]
    config = tmp_path / 'verifier.json'
    config.write_text(json.dumps({'keyPath': str(tmp_path / 'missing.json')}))
    with patch.dict(os.environ, {'API_TOKEN_VERIFIER': 'keys-test', 'VERIFIER_CONFIG_PATH': str(config)}):
        spec = importlib.util.spec_from_file_location('verifier_keys_test', root / 'apps/verifier/verifier.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        signature = bytes.fromhex(verifier.sign_with_verifier({'key': 'event-id'}))
        assert len(signature) == 64
        verifier.signing_key.public_key().verify(signature, verifier.canonical_json({'key': 'event-id'}).encode())
        assert verifier.batch_signer.private_key is verifier.signing_key
        verifier.manager_subscriptions.close()
