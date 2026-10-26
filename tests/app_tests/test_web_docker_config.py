"""Los destinos conservan su propio token al editar las filas del panel."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'web_docker_config_test', Path(__file__).resolve().parents[2] / 'tools/web_docker.py')
docker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docker)


def test_destination_tokens_follow_url_after_removal_and_reordering():
    original = {'services': {'verifiers': [
        {'url': 'http://first:5000', 'token': 'first-token'},
        {'url': 'http://second:5000', 'token': 'second-token'}]}}
    masked = docker.redact(original)
    masked['services']['verifiers'].reverse()
    assert docker.restore(masked, original)['services']['verifiers'][0]['token'] == 'second-token'
    masked['services']['verifiers'].pop()
    assert docker.restore(masked, original)['services']['verifiers'] == [
        {'url': 'http://second:5000', 'token': 'second-token'}]


def test_new_destination_does_not_inherit_another_peers_token():
    original = [{'url': 'http://first:5000', 'token': 'first-token'}]
    updated = [{'url': 'http://new:5000', 'token': docker.MASK}]
    assert docker.restore(updated, original) == [{'url': 'http://new:5000', 'token': ''}]
    updated[0]['token'] = 'new-token'
    assert docker.restore(updated, original)[0]['token'] == 'new-token'


def test_redact_masks_private_and_key_material_fields():
    masked = docker.redact({'privateKey': 'abc', 'secret_key': 'def', 'keyPath': '/run/x', 'port': 1})
    assert masked['privateKey'] == docker.MASK and masked['secret_key'] == docker.MASK
    assert masked['keyPath'] == '/run/x' and masked['port'] == 1


def test_secret_values_collects_secret_looking_environment_and_mounted_files(tmp_path):
    secret_file = tmp_path / 'identity.toml'
    secret_file.write_text('secret_key = "SABCDEF"\n')
    key_file = tmp_path / 'key.json'
    key_file.write_text('{"kty": "OKP", "crv": "Ed25519", "d": "PRIVATE-D", "x": "PUBLIC-X"}')
    record = {'environment': {'API_TOKEN_MANAGER': 'tok-1', 'PHONENDO_VERBOSE': 'true',
                              'STELLAR_SECRET_KEY': 'SXYZ', 'SOME_API_KEY': 'k-9'},
              'control': 'ctl', 'config': {'server': {'token': 'cfg-token'}},
              'secretFiles': [str(secret_file), str(key_file)]}
    values = docker.secret_values(record)
    for expected in ('tok-1', 'SXYZ', 'k-9', 'ctl', 'cfg-token', 'SABCDEF', 'PRIVATE-D'):
        assert expected in values
    assert 'true' not in values and 'PUBLIC-X' not in values


def test_mask_text_hides_every_secret_value_and_ignores_short_noise():
    assert docker.mask_text('uso tok-1 y SABCDEF', ['tok-1', 'SABCDEF', '']) == 'uso [oculto] y [oculto]'


def test_demo_file_only_accepts_paths_inside_deploy_demo():
    assert docker.demo_file('deploy/demo/verifier_demo_key.json').is_file()
    for bad in ('../etc/passwd', '/etc/passwd', 'deploy/demo/../../README.md', 'README.md'):
        try:
            docker.demo_file(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
