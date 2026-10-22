"""JSON contract across the Python core, C++ core and Manager transport."""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/reader/core/python'))
sys.path.insert(0, str(ROOT / 'apps/reader'))
from reader_core.observation import Observation
from linux.communication.manager_client import ManagerClient


def test_cpp_and_python_json_preserve_values(tmp_path):
    cpp = ROOT / 'apps/reader/core/cpp'
    source = tmp_path / 'json_test.cpp'
    source.write_text(r'''
#include "observation.h"
#include <iostream>
int main() {
    Observation observation("temperatura", "36.7", "2026-10-22T10:00:00+00:00",
        "patient-001", "termorreceptor", "Board A/ñ", "sensor\"\\\n\r\t\001",
        "CELSIUS", "obs-1");
    std::cout << observation.toJson();
}
''')
    binary = tmp_path / 'json_test'
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-I', str(cpp / 'include'),
                    str(source), *map(str, sorted((cpp / 'src').glob('*.cpp'))),
                    '-o', str(binary)], check=True, capture_output=True, text=True)
    actual = json.loads(subprocess.check_output([str(binary)], text=True))
    observation = Observation(
        observable_property='temperatura', simple_result='36.7',
        phenomenon_time=datetime(2026, 10, 22, 10, tzinfo=timezone.utc),
        feature_of_interest='patient-001', procedure='termorreceptor',
        device_id='Board A/ñ', sensor_id='sensor"\\\n\r\t\x01',
        unit='CELSIUS', observation_id='obs-1',
    )
    assert actual == observation.to_dict()


@pytest.mark.parametrize('value', [23, 36.7, True, '36.7', {'values': [1, 2]}])
def test_manager_sends_json_object(monkeypatch, value):
    observation = Observation('temperature', value, datetime(2026, 10, 22),
                              'room', 'test', device_id='board', sensor_id='temp')
    captured = {}

    class Response:
        ok = True
        status_code = 200
        text = 'Event accepted'

    def post(url, **kwargs):
        captured.update(json.loads(json.dumps(kwargs['json'])))
        return Response()

    monkeypatch.setattr('linux.communication.manager_client.requests.post', post)
    ManagerClient('http://manager', token='test').send_observation_json(
        observation.to_dict(), 'reader', 'board')
    assert captured['payloadFormat'] == 'application/json'
    assert captured['payload']['simple_result'] == value
    assert captured['payload']['device_id'] == 'board'
    assert captured['payload']['sensor_id'] == 'temp'
    assert captured['payload']['unit'] is None
    assert captured['payload']['phenomenon_time'].endswith('+00:00')
