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
