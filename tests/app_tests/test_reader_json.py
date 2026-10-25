"""JSON contract across the Python core, C++ core and Manager transport."""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/reader/python/core'))
sys.path.insert(0, str(ROOT / 'apps/reader'))
from reader_core.observation import Observation
from reader_server.serialization import observation_to_dict


def test_cpp_and_python_json_preserve_values(tmp_path):
    cpp = ROOT / 'apps/reader/cpp/core'
    source = tmp_path / 'json_test.cpp'
    source.write_text(r'''
#include "observation.h"
#include "reader_serialization.h"
#include <iostream>
int main() {
    Observation observation("temperatura", "36.7", "2026-10-22T10:00:00+00:00",
        "patient-001", "termorreceptor", "Board A/ñ", "sensor\"\\\n\r\t\001",
        "CELSIUS", "obs-1");
    std::cout << observationToJson(observation);
}
''')
    binary = tmp_path / 'json_test'
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-I', str(cpp / 'include'),
                    str(source), *map(str, sorted((cpp / 'src').glob('*.cpp'))),
                    '-I', str(ROOT / 'apps/reader/cpp/server/include'),
                    *map(str, sorted((ROOT / 'apps/reader/cpp/server/src').glob('*.cpp'))),
                    '-o', str(binary)], check=True, capture_output=True, text=True)
    actual = json.loads(subprocess.check_output([str(binary)], text=True))
    observation = Observation(
        observable_property='temperatura', simple_result='36.7',
        phenomenon_time=datetime(2026, 10, 22, 10, tzinfo=timezone.utc),
        feature_of_interest='patient-001', procedure='termorreceptor',
        device_id='Board A/ñ', sensor_id='sensor"\\\n\r\t\x01',
        unit='CELSIUS', observation_id='obs-1',
    )
    assert actual == observation_to_dict(observation)


@pytest.mark.parametrize('value', [23, 36.7, True, '36.7', {'values': [1, 2]}])
def test_json_preserves_native_values(value):
    observation = Observation('temperature', value, datetime(2026, 10, 22),
                              'room', 'test', device_id='board', sensor_id='temp')
    payload = json.loads(json.dumps(observation_to_dict(observation)))
    assert payload['simple_result'] == value
    assert payload['device_id'] == 'board'
    assert payload['phenomenon_time'].endswith('+00:00')


def test_core_emits_original_observation_without_serializing(monkeypatch):
    from reader_core.core import ReaderCore
    sent = []
    core = ReaderCore(reader_id='reader', on_observation=sent.append)
    observation = Observation('temperature', 24.6, datetime.now(timezone.utc),
                              '', '', device_id='board', sensor_id='temp')
    assert not hasattr(Observation, 'to_dict')
    assert core.ingest(observation)
    assert sent[0] is observation
    assert core.get_device('board').get_sensor('temp').procedure == ''
    created = core.create_observation('board', 'temp', value=25)
    assert len(sent) == 1
    assert created.simple_result == 25
    assert core.ingest(created)
    assert sent[1] is created


@pytest.mark.parametrize('field', ['device_id', 'sensor_id'])
@pytest.mark.parametrize('value', [None, '', '   '])
def test_core_rejects_missing_identity_without_mutation(field, value):
    from reader_core.core import ReaderCore
    core = ReaderCore(reader_id='reader')
    observation = Observation('temperature', 1, datetime.now(), '', '',
                              device_id='board', sensor_id='temp')
    setattr(observation, field, value)
    with pytest.raises(ValueError, match=field):
        core.ingest(observation)
    assert core.devices == {}
    assert getattr(observation, field) == value


def test_cpp_core_emits_observation_without_rebuilding(tmp_path):
    cpp = ROOT / 'apps/reader/cpp/core'
    source = tmp_path / 'core_test.cpp'
    source.write_text(r'''
#include "core.h"
#include <cassert>
static const Observation* received = nullptr;
static int count = 0;
bool output(const Observation& observation) {
    received = &observation;
    ++count;
    return true;
}
int main() {
    ReaderCore core("reader", true, true, output);
    Observation observation("temperature", "24.6", "timestamp", "", "",
                            "board", "temp", "C", "original-id");
    Observation invalid = observation;
    invalid.deviceId = "";
    assert(!core.ingest(invalid));
    assert(core.deviceCount() == 0);
    invalid = observation;
    invalid.sensorId = "";
    assert(!core.ingest(invalid));
    assert(core.deviceCount() == 0);
    assert(core.ingest(observation));
    assert(received == &observation);
    assert(received->observationId == "original-id");
    assert(core.getDevice("board")->getSensor("temp")->procedure.empty());
    Observation created;
    assert(core.createObservation("board", "temp", "25", "timestamp", &created));
    assert(count == 1);
    assert(created.simpleResult == "25");
    assert(core.ingest(created));
    assert(count == 2);
    ReaderCore standalone;
    assert(standalone.ingest(observation));
    ReaderCore strict("strict", false, false);
    assert(!strict.ingest(observation));
}
''')
    binary = tmp_path / 'core_test'
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-I', str(cpp / 'include'),
                    str(source), *map(str, sorted((cpp / 'src').glob('*.cpp'))),
                    '-I', str(ROOT / 'apps/reader/cpp/server/include'),
                    *map(str, sorted((ROOT / 'apps/reader/cpp/server/src').glob('*.cpp'))),
                    '-o', str(binary)], check=True, capture_output=True, text=True)
    subprocess.run([str(binary)], check=True)
