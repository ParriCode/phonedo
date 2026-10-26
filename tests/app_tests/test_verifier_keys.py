import base64
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]


def load_verifier(config):
    spec = importlib.util.spec_from_file_location('verifier_keys_test', ROOT / 'apps/verifier/verifier.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    return verifier


def test_verifier_refuses_to_start_without_its_key(tmp_path):
    """Sin clave no hay firma que el contrato acepte: falla claro, nunca con una clave inventada."""
    config = tmp_path / 'verifier.json'
    config.write_text(json.dumps({'keyPath': str(tmp_path / 'missing.json')}))
    with patch.dict(os.environ, {'API_TOKEN_VERIFIER': 'keys-test', 'VERIFIER_CONFIG_PATH': str(config)}):
        with pytest.raises(RuntimeError, match='tools/keys.sh'):
            load_verifier(config)


def test_verifier_signs_events_and_batches_with_the_key_file(tmp_path):
    key = Ed25519PrivateKey.generate()
    key_file = tmp_path / 'verifier-a.json'
    key_file.write_text(json.dumps({'kty': 'OKP', 'crv': 'Ed25519', 'd': base64.urlsafe_b64encode(key.private_bytes_raw()).decode().rstrip('=')}))
    config = tmp_path / 'verifier.json'
    config.write_text(json.dumps({'keyPath': str(key_file)}))
    with patch.dict(os.environ, {'API_TOKEN_VERIFIER': 'keys-test', 'VERIFIER_CONFIG_PATH': str(config)}):
        verifier = load_verifier(config)
        try:
            assert verifier.verifier_id == key.public_key().public_bytes_raw().hex()
            signature = bytes.fromhex(verifier.sign_with_verifier({'key': 'event-id'}))
            key.public_key().verify(signature, verifier.canonical_json({'key': 'event-id'}).encode())
            assert verifier.batch_signer.private_key is verifier.signing_key
        finally:
            verifier.manager_subscriptions.close()
