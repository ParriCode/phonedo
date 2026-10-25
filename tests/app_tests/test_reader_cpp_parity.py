"""Paridad del Reader C++ portable con la especificación Python.

Python es la referencia: cada prueba compila un programa C++ en el host con
-DARDUINO (sin SDK de Arduino) y compara su JSON con el que produce Python.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / 'apps/reader'
sys.path.insert(0, str(READER / 'python/core'))
sys.path.insert(0, str(READER / 'python/server'))
from reader_core import Device, Observation, ReaderCore, Sensor
from reader_server import ReaderService
from reader_server.serialization import observation_event, observation_to_dict


def run_cpp(tmp_path, code):
    """Compila contra core + server y devuelve la salida estándar."""
    source = tmp_path / 'parity.cpp'
    source.write_text(code)
    binary = tmp_path / 'parity'
    command = ['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-DARDUINO']
    for layer in ('core', 'server'):
        command += ['-I', str(READER / 'cpp' / layer / 'include')]
    command.append(str(source))
    for layer in ('core', 'server'):
        command += map(str, sorted((READER / 'cpp' / layer / 'src').glob('*.cpp')))
    built = subprocess.run([*command, '-o', str(binary)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    return subprocess.run([str(binary)], check=True, capture_output=True, text=True).stdout


def lines(output):
    return [json.loads(line) for line in output.splitlines() if line.strip()]


# T1: payload con tipos nativos, hora ISO UTC y unit nula.

TIME_MS = 1792663200123  # 2026-10-22T10:00:00.123+00:00
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
TIME = EPOCH + timedelta(milliseconds=TIME_MS)


def python_payload(value, unit=None):
    return observation_to_dict(Observation(
        'temperature', value, TIME, 'room', 'measure',
        device_id='board', sensor_id='temp', unit=unit, observation_id='obs'))


def test_cpp_typed_simple_result_matches_python(tmp_path):
    output = run_cpp(tmp_path, r'''
#include "reader_serialization.h"
#include <iostream>
int main() {
    Observation base("temperature", "", isoUtcFromEpochMillis(1792663200123LL), "room",
                     "measure", "board", "temp", "", "obs");
    Observation value = base;
    value.setInteger(23);                     std::cout << observationToJson(value) << "\n";
    value.setNumber(36.7);                    std::cout << observationToJson(value) << "\n";
    value.setNumber(0.1);                     std::cout << observationToJson(value) << "\n";
    value.setInteger(-9007199254740993LL);    std::cout << observationToJson(value) << "\n";
    value.setBoolean(true);                   std::cout << observationToJson(value) << "\n";
    value.setBoolean(false);                  std::cout << observationToJson(value) << "\n";
    value.setText("36.7");                    std::cout << observationToJson(value) << "\n";
    value.setNull();                          std::cout << observationToJson(value) << "\n";
    value.setRawJson("{\"values\":[1,2]}");   std::cout << observationToJson(value) << "\n";
    value.setRawJson("");                     std::cout << observationToJson(value) << "\n";
    value.setNumber(36.7);
    value.unit = "CELSIUS";                   std::cout << observationToJson(value) << "\n";
}
''')
    expected = [python_payload(v) for v in
                (23, 36.7, 0.1, -9007199254740993, True, False, '36.7', None, {'values': [1, 2]}, None)]
    expected.append(python_payload(36.7, 'CELSIUS'))
    actual = lines(output)
    assert actual == expected
    # El tipo nativo importa: 23 no es "23" ni true es 1.
    assert type(actual[0]['simple_result']) is int
    assert actual[4]['simple_result'] is True
    assert actual[0]['unit'] is None


def test_cpp_string_constructor_keeps_text_result(tmp_path):
    # La API existente (simpleResult de texto) sigue serializando una cadena.
    output = run_cpp(tmp_path, r'''
#include "reader_serialization.h"
#include <cassert>
#include <iostream>
int main() {
    Observation value("motion", "true", "2026-10-22T10:00:00+00:00", "room", "pir", "board", "pir");
    assert(value.resultType == ResultType::Text);
    std::cout << observationToJson(value) << "\n";
    value.setBoolean(true);
    assert(value.simpleResult == "true");
    assert(value.resultType == ResultType::Boolean);
}
''')
    assert lines(output)[0]['simple_result'] == 'true'


@pytest.mark.parametrize('millis', [0, 1, 999, 951782400000, 1709164800500,
                                    TIME_MS, 4102444799999, -1])
def test_cpp_iso_utc_matches_python_isoformat(tmp_path, millis):
    output = run_cpp(tmp_path, r'''
#include "observation.h"
#include <iostream>
int main() { std::cout << isoUtcFromEpochMillis(%dLL) << "\n"; }
''' % millis)
    expected = (EPOCH + timedelta(milliseconds=millis)).isoformat()
    assert output.strip() == expected


def test_cpp_phenomenon_time_normalized_like_python(tmp_path):
    output = run_cpp(tmp_path, r'''
#include "reader_serialization.h"
#include <iostream>
int main() {
    const char* times[] = {"2026-10-22T10:00:00", "2026-10-22T10:00:00Z",
                           "2026-10-22T10:00:00.250000", "2026-10-22T12:00:00+02:00",
                           "1792663200123", "timestamp"};
    for (const char* time : times) {
        Observation value("temperature", "1", time, "room", "measure", "board", "temp", "", "obs");
        std::cout << observationToJson(value) << "\n";
    }
}
''')
    times = [row['phenomenon_time'] for row in lines(output)]

    def python_time(moment):
        return observation_to_dict(Observation('t', 1, moment, '', '', 'b', 's'))['phenomenon_time']

    assert times[0] == python_time(datetime(2026, 10, 22, 10))
    assert times[1] == python_time(datetime(2026, 10, 22, 10, tzinfo=timezone.utc))
    assert times[2] == python_time(datetime(2026, 10, 22, 10, 0, 0, 250000))
    assert times[3] == '2026-10-22T12:00:00+02:00'
    assert times[4] == TIME.isoformat()
    # Lo que no es una hora reconocible se conserva tal cual.
    assert times[5] == 'timestamp'


def test_cpp_observation_event_envelope_matches_python(tmp_path):
    output = run_cpp(tmp_path, r'''
#include "reader_serialization.h"
#include <iostream>
int main() {
    Observation value("temperature", "", isoUtcFromEpochMillis(1792663200123LL), "room",
                      "measure", "board \"A\"", "temp", "C", "obs");
    value.setNumber(24.5);
    std::cout << observationEventToJson("reader-1", value) << "\n";
}
''')
    observation = Observation('temperature', 24.5, TIME, 'room', 'measure',
                              device_id='board "A"', sensor_id='temp', unit='C',
                              observation_id='obs')
    assert lines(output) == [observation_event('reader-1', observation)]


# T2: ReaderService con metadata, devices y device.

def test_cpp_service_refuses_core_with_existing_callback(tmp_path):
    with pytest.raises(ValueError, match='callbacks'):
        ReaderService(ReaderCore(on_observation=lambda _: None))
    run_cpp(tmp_path, r'''
#include "reader_service.h"
#include <cassert>
static int previous = 0;
int main() {
    ReaderCore taken("reader", true, true, [](const Observation&) { ++previous; return true; });
    assert(taken.hasOnObservationCallback());
    {
        ReaderService refused(taken);
        assert(!refused.isAttached());
        assert(refused.getLastError().find("callbacks") != std::string::npos);
        Observation value("temperature", "1", "t", "room", "measure", "board", "temp");
        assert(!refused.ingest(value));
        assert(previous == 0);
    }
    // El servicio rechazado no toca la callback ajena, ni al destruirse.
    assert(taken.hasOnObservationCallback());
    Observation value("temperature", "1", "t", "room", "measure", "board", "temp");
    assert(taken.ingest(value));
    assert(previous == 1);

    ReaderCore fresh("reader");
    {
        ReaderService service(fresh);
        assert(service.isAttached());
        assert(service.getLastError().empty());
        assert(fresh.hasOnObservationCallback());
    }
    assert(!fresh.hasOnObservationCallback());
}
''')


def test_cpp_service_metadata_and_devices_match_python(tmp_path):
    output = run_cpp(tmp_path, r'''
#include "reader_service.h"
#include <cassert>
#include <iostream>
int main() {
    ReaderCore core("reader-1");
    ReaderService service(core);
    std::cout << service.metadataJson(true) << "\n";
    std::cout << service.metadataJson(false) << "\n";
    std::cout << service.devicesJson() << "\n";
    Device board("board", "ESP32", "arduino");
    Sensor temp("temperature", "measure", "room", "temp", "C");
    Sensor hum("humidity", "measure", "room", "hum");
    assert(board.addSensor(temp) && board.addSensor(hum));
    assert(core.addDevice(board));
    Observation value("motion", "true", "t", "room", "pir", "dynamic", "pir");
    assert(service.ingest(value));
    std::cout << service.devicesJson() << "\n";
    std::string device;
    assert(service.deviceJson("board", device));
    std::cout << device << "\n";
    board.creationDatetime = "2026-10-22T10:00:00+00:00";
    assert(service.deviceJson("board", device));
    std::cout << device << "\n";
    std::string untouched = "keep";
    assert(!service.deviceJson("missing", untouched));
    assert(untouched == "keep");
    assert(!service.deviceJson("", untouched));
}
''')
    rows = lines(output)

    core = ReaderCore('reader-1')
    python = ReaderService(core)
    assert rows[0] == python.metadata(stream_enabled=True)
    assert rows[1] == python.metadata(stream_enabled=False)
    assert rows[2] == python.devices() == []

    board = Device('board', 'ESP32', platform='arduino')
    board.add_sensor(Sensor('temperature', 'measure', 'room', sensor_id='temp', unit='C'))
    board.add_sensor(Sensor('humidity', 'measure', 'room', sensor_id='hum'))
    core.add_device(board)
    python.ingest(Observation('motion', True, datetime.now(timezone.utc), 'room', 'pir',
                              device_id='dynamic', sensor_id='pir'))
    assert rows[3] == python.devices()

    # Python lee un creation_datetime inexistente; C++ emite null si no hay fecha.
    expected = {'schemaVersion': 'phonendo.device.v1', 'readerId': 'reader-1',
                'deviceId': 'board', 'deviceType': 'ESP32', 'creationDatetime': None,
                'sensors': ['temp', 'hum']}
    assert rows[4] == expected
    assert rows[5] == {**expected, 'creationDatetime': '2026-10-22T10:00:00+00:00'}


# T3: stream con colas acotadas y formato SSE.

def test_cpp_stream_bounded_queues_and_slow_subscriber(tmp_path):
    run_cpp(tmp_path, r'''
#include "reader_stream.h"
#include <cassert>
int main() {
    ObservationStream invalid(0);
    assert(!invalid.isValid());
    assert(invalid.subscribe() == 0);
    assert(!invalid.getLastError().empty());

    ObservationStream stream(2);
    assert(stream.isValid());
    SubscriberId fast = stream.subscribe();
    SubscriberId slow = stream.subscribe();
    assert(fast != 0 && slow != 0 && fast != slow);
    assert(stream.subscriberCount() == 2);

    std::string event;
    assert(stream.poll(fast, event) == StreamPoll::Empty);
    stream.publish("a");
    stream.publish("b");
    assert(stream.pending(slow) == 2);
    assert(stream.poll(fast, event) == StreamPoll::Event && event == "a");
    assert(stream.poll(fast, event) == StreamPoll::Event && event == "b");

    // La cola de slow está llena: el siguiente evento la desconecta y la vacía.
    stream.publish("c");
    assert(stream.subscriberCount() == 1);
    assert(stream.pending(slow) == 0);
    assert(stream.poll(slow, event) == StreamPoll::Closed);
    assert(stream.poll(slow, event) == StreamPoll::Unknown);
    assert(stream.poll(fast, event) == StreamPoll::Event && event == "c");

    // Darse de baja sin cierre.
    SubscriberId gone = stream.subscribe();
    stream.unsubscribe(gone);
    assert(stream.poll(gone, event) == StreamPoll::Unknown);

    // close() desconecta a todos; se puede volver a suscribir después.
    stream.publish("d");
    stream.close();
    assert(stream.subscriberCount() == 0);
    assert(stream.poll(fast, event) == StreamPoll::Closed);
    SubscriberId again = stream.subscribe();
    stream.publish("e");
    assert(stream.poll(again, event) == StreamPoll::Event && event == "e");
}
''')


def test_cpp_stream_output_publishes_python_envelopes(tmp_path):
    output = run_cpp(tmp_path, r'''
#include "reader_service.h"
#include "reader_stream.h"
#include <cassert>
#include <iostream>
int main() {
    ObservationStream stream(4);
    StreamOutput output(stream);
    ReaderCore core("reader-1");
    ReaderService service(core, {&output});
    SubscriberId id = stream.subscribe();
    Observation value("temperature", "", isoUtcFromEpochMillis(1792663200123LL), "room",
                      "measure", "board", "temp", "", "obs");
    value.setInteger(23);
    assert(service.ingest(value));
    std::string event;
    assert(stream.poll(id, event) == StreamPoll::Event);
    std::cout << event << "\n";
    std::cout << sseObservation(event);
}
''')
    observation = Observation('temperature', 23, TIME, 'room', 'measure',
                              device_id='board', sensor_id='temp', observation_id='obs')
    envelope, sse = output.split('\n', 1)
    assert json.loads(envelope) == observation_event('reader-1', observation)
    assert sse.startswith('event: observation\ndata: ') and sse.endswith('\n\n')
    assert json.loads(sse[len('event: observation\ndata: '):-2]) == json.loads(envelope)


def test_cpp_sse_framing_matches_python_server(tmp_path):
    output = run_cpp(tmp_path, r'''
#include "reader_stream.h"
#include <iostream>
int main() {
    std::cout << sseConnected() << sseHeartbeat() << sseStreamClosed() << "|"
              << PHONENDO_SSE_HEARTBEAT_MS;
}
''')
    framing, heartbeat = output.split('|')
    assert framing == ': connected\n\n: heartbeat\n\nevent: stream_closed\ndata: {}\n\n'
    assert int(heartbeat) == 15000
