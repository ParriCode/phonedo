"""tools/keys.py: claves de Verifier y carteras de Publisher en keys/."""
import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def keys(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('keys_under_test', ROOT / 'tools/keys.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'VERIFIERS', tmp_path / 'keys/verifiers')
    monkeypatch.setattr(module, 'STELLAR', tmp_path / 'keys/stellar')
    monkeypatch.setattr(module, 'WALLETS', tmp_path / 'keys/stellar/identity')
    monkeypatch.setattr(module, 'LEGACY_VERIFIER', (tmp_path / 'circuits/build/verifier_dev_key.json',))
    monkeypatch.setattr(module, 'CLI_WALLETS', tmp_path / 'cli')
    monkeypatch.setattr(module, 'fund', lambda address: True)
    return module


def test_strkey_round_trip_matches_the_verifier(keys):
    raw = bytes(range(32))
    assert keys.strkey_payload(6 << 3, keys.strkey(6 << 3, raw)) == raw
    assert keys.strkey(6 << 3, bytes(32)) == 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF'
    with pytest.raises(ValueError):
        keys.strkey_payload(18 << 3, keys.strkey(6 << 3, raw))


def test_init_reuses_previous_keys_and_never_overwrites(keys, tmp_path):
    legacy = tmp_path / 'circuits/build/verifier_dev_key.json'
    legacy.parent.mkdir(parents=True)
    key = Ed25519PrivateKey.generate()
    legacy.write_text(json.dumps({'kty': 'OKP', 'crv': 'Ed25519', 'd': keys.b64(key.private_bytes_raw()),
                                  'x': keys.b64(key.public_key().public_bytes_raw())}))
    (tmp_path / 'cli').mkdir()
    (tmp_path / 'cli/phonendo.toml').write_text('seed_phrase = "palabras de prueba"\n')
    notes = keys.init()
    assert len(notes) == 2
    assert keys.verifier_id(keys.verifier_path('dev')) == key.public_key().public_bytes_raw().hex()
    assert keys.wallet_path('phonendo').read_text() == 'seed_phrase = "palabras de prueba"\n'
    assert keys.wallet_path('phonendo').stat().st_mode & 0o777 == 0o600
    assert keys.init() == []


def test_regenerate_wallets_keeps_a_backup_and_new_verifiers_are_distinct(keys):
    keys.init()
    old = keys.wallet_address('phonendo')
    notes = keys.init(regenerate_wallets=True)
    assert keys.wallet_address('phonendo') != old and old not in ''.join(notes)
    assert len(list(keys.WALLETS.glob('phonendo.toml.*.bak'))) == 1
    keys.new_verifier('verifier-b')
    with pytest.raises(ValueError, match='--force'):
        keys.new_verifier('verifier-b')
    ids = {item['verifierId'] for item in keys.inventory()['verifiers']}
    assert len(ids) == 2


def test_inventory_only_exposes_public_parts(keys):
    keys.init()
    secret = keys.wallet_path('phonendo').read_text()
    listed = json.dumps(keys.inventory())
    assert 'S' + secret.split('"S', 1)[1][:20] not in listed
    assert json.loads(keys.verifier_path('dev').read_text())['d'] not in listed
    with pytest.raises(ValueError):
        keys.verifier_path('../fuera')


def test_check_reports_which_of_your_keys_a_contract_trusts(keys, monkeypatch):
    keys.init()
    mine = keys.verifier_id(keys.verifier_path('dev'))

    def contract(trusted):
        instance = {'contract_instance': {'storage': [{'key': {'vec': [{'symbol': 'Config'}]}, 'val': {'map': [
            {'key': {'symbol': 'admin'}, 'val': {'address': 'G'}},
            {'key': {'symbol': 'verifier_key'}, 'val': {'bytes': trusted}}]}}]}}
        row = '"""ledger_key_contract_instance""","' + json.dumps(instance).replace('"', '""') + '"\n'
        return type('Result', (), {'returncode': 0, 'stdout': row, 'stderr': ''})()

    monkeypatch.setattr(keys.subprocess, 'run', lambda *a, **k: contract(mine))
    assert keys.check_contract('CONTRACT') == (mine, ['dev'])
    monkeypatch.setattr(keys.subprocess, 'run', lambda *a, **k: contract('f8' * 32))
    assert keys.check_contract('CONTRACT') == ('f8' * 32, [])
    assert keys.main(['verifier', 'check', 'CONTRACT']) == 2
