"""Layer boundaries and the shared Reader contract, without hardware."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pytest

from reader_core import ReaderCore, Observation
from reader_server import ReaderService

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / 'apps/reader'


def observation():
    return Observation('temperature', 23, datetime.now(timezone.utc), 'room', 'measure',
                       device_id='board', sensor_id='temperature')


def test_python_layers_load_without_site_packages_or_platform(tmp_path):
    # -I -S removes the working directory, environment paths and installed packages.
    code = '''
import sys
sys.path[:0] = sys.argv[1:]
from reader_core import ReaderCore, Observation
from reader_server import ReaderService
from datetime import datetime
core = ReaderCore('standalone')
service = ReaderService(core)
assert service.ingest(Observation('temperature', 23, datetime.now(), 'room', 'measure',
                                  device_id='board', sensor_id='temp'))
assert not hasattr(Observation, 'to_dict')
assert not hasattr(core, 'load_devices_from_config')
assert not hasattr(core, 'handle_serial_data')
assert not hasattr(core, 'handle_bluetooth_data')
for module in ('aiohttp', 'requests', 'serial', 'bleak', 'logger', 'examples'):
    assert module not in sys.modules, module
'''
    subprocess.run([sys.executable, '-I', '-S', '-c', code,
                    str(READER / 'python/core'), str(READER / 'python/server')],
                   cwd=tmp_path, check=True, capture_output=True, text=True)


def test_service_fanout_uses_model_objects_and_reader_identity():
    calls = []

    class Output:
        def register_device(self, reader_id, device):
            calls.append(('register', reader_id, device))

        def publish(self, reader_id, value):
            calls.append(('observation', reader_id, value))

    core = ReaderCore('reader')
    service = ReaderService(core, (Output(), Output()))
    value = observation()
    assert service.ingest(value)
    assert [call[0] for call in calls] == ['register', 'register', 'observation', 'observation']
    assert all(call[1] == 'reader' for call in calls)
    assert calls[2][2] is value and calls[3][2] is value
    assert service.devices() == [{'deviceId': 'board', 'deviceType': 'device', 'sensors': ['temperature']}]
    assert service.metadata()['readerId'] == 'reader'
    assert core.remove_device('board')
    assert service.devices() == []


def test_service_rejects_overwriting_existing_core_callbacks():
    core = ReaderCore(on_observation=lambda _: None)
    with pytest.raises(ValueError, match='callbacks'):
        ReaderService(core)


def compile_cpp(tmp_path, code, *, server=False):
    source = tmp_path / 'test.cpp'
    source.write_text(code)
    core = READER / 'cpp/core'
    binary = tmp_path / 'test'
    # Defining ARDUINO must not pull Arduino.h into the portable libraries.
    command = ['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-DARDUINO',
               '-I', str(core / 'include'), str(source), *map(str, sorted((core / 'src').glob('*.cpp')))]
    if server:
        layer = READER / 'cpp/server'
        command += ['-I', str(layer / 'include'), *map(str, sorted((layer / 'src').glob('*.cpp')))]
    subprocess.run([*command, '-o', str(binary)], check=True, capture_output=True, text=True)
    subprocess.run([str(binary)], check=True)


def test_cpp_core_builds_without_server_or_arduino_sdk(tmp_path):
    compile_cpp(tmp_path, r'''
#include "core.h"
#include <cassert>
int main() {
    ReaderCore core("reader");
    Device device("board");
    int registrations = 0;
    core.setOnRegisterCallback([&](Device&) { ++registrations; });
    assert(core.addDevice(device));
    assert(registrations == 0);
    assert(core.getDevice("board") == &device);
    assert(core.removeDevice("board"));
    assert(core.registerDevice(device));
    assert(registrations == 1);
    Observation value("temperature", "23", "timestamp", "room", "measure", "board", "temp");
    assert(core.ingest(value));
    assert(core.sendObservation(value));
    assert(core.removeDevice("board"));
    assert(!core.sendObservation(value));
}
''')


def test_cpp_service_routes_observations_to_platform_ports(tmp_path):
    compile_cpp(tmp_path, r'''
#include "reader_service.h"
#include <cassert>
struct Output : ObservationOutput {
    int registered = 0;
    int emitted = 0;
    const Observation* last = nullptr;
    void registerDevice(const std::string& readerId, const Device& device) override {
        assert(readerId == "reader" && device.deviceId == "board");
        ++registered;
    }
    bool publish(const std::string& readerId, const Observation& observation) override {
        assert(readerId == "reader");
        last = &observation;
        ++emitted;
        return true;
    }
};
int main() {
    Output first, second;
    ReaderCore core("reader");
    ReaderService service(core, {&first, &second});
    assert(&service.core() == &core);
    Observation value("temperature", "23", "timestamp", "room", "measure", "board", "temp");
    assert(service.ingest(value));
    assert(first.registered == 1 && second.registered == 1);
    assert(first.emitted == 1 && second.emitted == 1);
    assert(first.last == &value && second.last == &value);
    assert(service.core().removeDevice("board"));
    assert(service.core().deviceCount() == 0);
}
''', server=True)



@pytest.mark.parametrize('stream_enabled', [True, False])
def test_server_lifecycle_and_http(stream_enabled):
    from aiohttp import ClientSession
    from reader_server import ReaderServer, ServerConfig

    async def check():
        core = ReaderCore('lifecycle')
        server = ReaderServer(core, ServerConfig(enabled=True, port=0,
                                                 stream_enabled=stream_enabled))
        assert (server.stream is not None) == stream_enabled
        assert len(server.service.outputs) == int(stream_enabled)
        assert not server.running
        await server.start()
        runner = server.runner
        await server.start()
        assert server.runner is runner
        assert server.status()['running']
        port = runner.addresses[0][1]
        try:
            async with ClientSession() as client:
                async with client.get(f'http://127.0.0.1:{port}/metadata') as response:
                    assert response.status == 200
                    assert (await response.json())['capabilities']['stream'] == stream_enabled
                if not stream_enabled:
                    async with client.get(f'http://127.0.0.1:{port}/stream') as response:
                        assert response.status == 404
            assert core.ingest(observation())
        finally:
            await server.stop()
        await server.stop()
        assert not server.running
        assert server.runner is None
        with pytest.raises(RuntimeError, match='disposed'):
            await server.start()
    asyncio.run(check())


def test_disabled_server_and_no_outputs():
    from reader_server import ReaderServer, ServerConfig
    core = ReaderCore('disabled')
    server = ReaderServer(core, ServerConfig(stream_enabled=False))
    assert server.stream is None
    assert server.service.outputs == ()
    assert core.ingest(observation())
    with pytest.raises(RuntimeError, match='disabled'):
        _ = server.app
    async def check():
        await server.start()
        await server.start()
        assert not server.running
        await server.stop()
        await server.stop()
    asyncio.run(check())


def test_cpp_service_detaches_from_external_core(tmp_path):
    compile_cpp(tmp_path, r'''
#include "reader_service.h"
#include <cassert>
struct Output : ObservationOutput {
    int calls = 0;
    void registerDevice(const std::string&, const Device&) override {}
    bool publish(const std::string&, const Observation&) override { ++calls; return true; }
};
int main() {
    ReaderCore core("reader");
    Output output;
    Observation value("temperature", "23", "timestamp", "room", "measure", "board", "temp");
    {
        ReaderService service(core, {&output});
        assert(core.ingest(value));
        assert(output.calls == 1);
    }
    assert(core.ingest(value));
    assert(output.calls == 1);
    assert(core.getDevice("board") != nullptr);
}
''', server=True)


def test_http_partial_start_cleans_up():
    import socket
    from reader_server import ReaderServer, ServerConfig
    async def check():
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            server = ReaderServer(ReaderCore('failure'), ServerConfig(
                enabled=True, port=occupied.getsockname()[1]))
            with pytest.raises(OSError):
                await server.start()
            assert not server.running
            assert server.runner is None
            await server.stop()
    asyncio.run(check())
