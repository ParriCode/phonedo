"""Transport tests use loopback HTTP and fake sources; no hardware is needed."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading

from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/reader"))
from argparse import Namespace
from implementations.linux.main import load_settings, build_app, run_app


def Reader(id=None, config_file="devices_and_sensors.json", verbose=None, static=False):
    return build_app(load_settings(Namespace(
        reader_id=id, config=config_file, verbose=verbose, static=static)))

from reader_server.stream import ObservationStream
from implementations.linux.sources.local_metrics import LocalMetricsSource
from reader_core.core import ReaderCore
from reader_core.observation import Observation


def observation():
    return Observation(
        observable_property="temperature", simple_result=23,
        phenomenon_time=datetime.now(timezone.utc),
        feature_of_interest="room", procedure="test",
        device_id="sensor-board", sensor_id="temperature",
    )


def reader_config(tmp_path, communication):
    path = tmp_path / "reader.json"
    path.write_text(json.dumps({
        "reader_id": "stream-reader",
        "communication": communication,
        "sources": {"serial": {"enabled": False}},
    }))
    return path


def test_core_without_communication():
    core = ReaderCore(reader_id="standalone")
    assert core.ingest(observation())
    assert core.get_device("sensor-board").has_sensor("temperature")


def test_stream_fanout_and_slow_consumer():
    async def check():
        stream = ObservationStream(queue_size=1)
        with stream.subscribe() as fast, stream.subscribe() as slow:
            stream.publish({"value": 1})
            assert await fast.get() == {"value": 1}
            stream.publish({"value": 2})
            assert await fast.get() == {"value": 2}
            assert await slow.get() is None
            stream.publish({"value": 3})
            assert await fast.get() == {"value": 3}
            assert slow.empty()
        assert not stream._subscribers
    asyncio.run(check())


def test_http_stream_without_manager(tmp_path):
    async def check():
        reader = Reader(config_file=str(reader_config(tmp_path, {
            "server": {"enabled": True, "token": "test-token"},
        })))
        assert reader.manager_output is None
        async with TestClient(TestServer(reader.server.app)) as client:
            response = await client.get("/metadata")
            assert response.status == 401
            headers = {"Authorization": "Bearer test-token"}
            response = await client.get("/metadata", headers=headers)
            assert (await response.json())["readerId"] == "stream-reader"
            first = await client.get("/observations/stream", headers=headers)
            second = await client.get("/observations/stream", headers=headers)
            for response in (first, second):
                assert await response.content.readline() == b": connected\n"
                assert await response.content.readline() == b"\n"
            reader.core.ingest(observation())
            for response in (first, second):
                assert await asyncio.wait_for(response.content.readline(), 1) == b"event: observation\n"
                event = json.loads((await response.content.readline()).decode()[6:])
                assert event["deviceId"] == "sensor-board"
                assert event["payload"]["simple_result"] == 23
                assert event["payloadFormat"] == "application/json"
            response = await client.get("/devices", headers=headers)
            assert (await response.json())[0]["sensors"] == ["temperature"]
            reader.server.stream.close()
            first.close()
            second.close()
    asyncio.run(check())


def test_stream_can_be_disabled(tmp_path):
    async def check():
        reader = Reader(config_file=str(reader_config(tmp_path, {
            "server": {"enabled": True, "stream_enabled": False},
        })))
        async with TestClient(TestServer(reader.server.app)) as client:
            assert (await client.get("/observations/stream")).status == 404
            response = await client.get("/metadata")
            assert (await response.json())["capabilities"]["stream"] is False
    asyncio.run(check())


def test_manager_delivery_does_not_block_stream(tmp_path):
    async def check():
        reader = Reader(config_file=str(reader_config(tmp_path, {
            "manager": {"enabled": True},
        })))
        started, release = threading.Event(), threading.Event()
        calls = []

        def register(reader_id, device):
            calls.append("register")
            started.set()
            release.wait(2)

        reader.manager_output.client.register_device = register
        reader.manager_output.client.send_observation_json = lambda *args: calls.append("send")
        worker = asyncio.create_task(reader.manager_output.run())
        try:
            with reader.server.stream.subscribe() as stream:
                reader.core.ingest(observation())
                assert await asyncio.wait_for(asyncio.to_thread(started.wait, 1), 2)
                assert (await asyncio.wait_for(stream.get(), 0.2))["deviceId"] == "sensor-board"
                assert calls == ["register"]
                release.set()
                await asyncio.wait_for(reader.manager_output.queue.join(), 2)
                assert calls == ["register", "send"]
        finally:
            release.set()
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
    asyncio.run(check())


def test_manager_can_send_without_registration(tmp_path):
    async def check():
        reader = Reader(config_file=str(reader_config(tmp_path, {
            "manager": {"enabled": True, "register_devices": False},
        })))
        sent = []
        reader.manager_output.client.send_observation_json = lambda *args: sent.append(args)
        reader.manager_output.client.register_device = lambda *args: (_ for _ in ()).throw(
            AssertionError("Registration disabled"))
        reader.core.ingest(observation())
        await reader.manager_output.deliver_next()
        assert len(sent) == 1
    asyncio.run(check())


def test_local_metrics_emit_core_observations():
    async def check():
        captured = []
        source = LocalMetricsSource(captured.append, device_id="my-host")
        now = datetime.now(timezone.utc)
        await source.emit("cpu", 42, "%", now)
        assert isinstance(captured[0], Observation)
        assert captured[0].device_id == "my-host"
        assert captured[0].simple_result == 42
        assert captured[0].phenomenon_time == now
    asyncio.run(check())


def test_runtime_cancellation_stops_sources(tmp_path):
    async def check():
        reader = Reader(config_file=str(reader_config(tmp_path, {})))
        started = asyncio.Event()
        stopped = []

        class FakeSource:
            async def start(self):
                started.set()
                await asyncio.Event().wait()

            async def stop(self):
                stopped.append(True)

        reader.sources = [FakeSource()]
        task = asyncio.create_task(run_app(reader))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert stopped == [True]
    asyncio.run(check())
