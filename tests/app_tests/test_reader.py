"""Minimal Linux example: emits simulated observations and closes on cancellation."""
import asyncio
from examples.linux import main as example
from reader_server import ReaderServer, ServerConfig


def test_linux_example_stream_and_cleanup(monkeypatch):
    async def check():
        created = []
        def server(core, config):
            instance = ReaderServer(core, ServerConfig(enabled=True, port=0))
            created.append(instance)
            return instance
        monkeypatch.setattr(example, 'ReaderServer', server)
        task = asyncio.create_task(example.main())
        try:
            for _ in range(100):
                if created and created[0].running:
                    break
                await asyncio.sleep(.01)
            assert created and created[0].running
            with created[0].stream.subscribe() as queue:
                event = await asyncio.wait_for(queue.get(), 2)
            payload = event['payload']
            assert payload['procedure'] == 'random-simulation'
            assert 20 <= payload['simple_result'] <= 30
            assert payload['unit'] == 'CELSIUS'
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        assert not created[0].running
        assert created[0].runner is None
    asyncio.run(check())


def test_simulation_settings_defaults_presets_and_overrides():
    assert example.simulation_settings({})['property'] == 'temperature'
    pulse = example.simulation_settings({'simulation': 'pulse'})
    assert (pulse['property'], pulse['unit'], pulse['min'], pulse['max']) == ('heart_rate', 'BPM', 95, 120)
    custom = example.simulation_settings({'simulation': {'min': 60, 'max': 70}})
    assert (custom['min'], custom['max'], custom['unit']) == (60, 70, 'CELSIUS')
