"""HTTP and stream behavior independent of platform adapters."""
import asyncio
import json
from datetime import datetime, timezone
from aiohttp.test_utils import TestClient, TestServer
from reader_core import ReaderCore, Observation
from reader_server import ReaderServer, ServerConfig
from reader_server.stream import ObservationStream


def observation():
    return Observation('temperature', 23, datetime.now(timezone.utc), 'room', 'test',
                       device_id='sensor-board', sensor_id='temperature')


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
        core = ReaderCore('stream-reader')
        server = ReaderServer(core, ServerConfig(enabled=True, token='test-token'))
        async with TestClient(TestServer(server.app)) as client:
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
            core.ingest(observation())
            for response in (first, second):
                assert await asyncio.wait_for(response.content.readline(), 1) == b"event: observation\n"
                event = json.loads((await response.content.readline()).decode()[6:])
                assert event["deviceId"] == "sensor-board"
                assert event["payload"]["simple_result"] == 23
                assert event["payloadFormat"] == "application/json"
            response = await client.get("/devices", headers=headers)
            assert (await response.json())[0]["sensors"] == ["temperature"]
            server.stream.close()
            first.close()
            second.close()
    asyncio.run(check())


def test_stream_can_be_disabled(tmp_path):
    async def check():
        core = ReaderCore('stream-reader')
        server = ReaderServer(core, ServerConfig(enabled=True, stream_enabled=False))
        async with TestClient(TestServer(server.app)) as client:
            assert (await client.get("/observations/stream")).status == 404
            response = await client.get("/metadata")
            assert (await response.json())["capabilities"]["stream"] is False
    asyncio.run(check())
