"""Interactive Reader process used exclusively by the local lab UI."""
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/reader/python/core'), str(ROOT / 'apps/reader/python/server')]
from reader_core import ReaderCore, Device, Sensor
from reader_server import ReaderServer, ServerConfig, ManagerOutput


async def run(path):
    config = json.loads(Path(path).read_text())
    core = ReaderCore(config.get('readerId', 'reader-lab'))
    output = ManagerOutput(config.get('services', {}).get('managers', []))
    server_settings = dict(config['server'])
    server_settings['stream_enabled'] = config.get('stream', {}).get('enabled', True)
    server = ReaderServer(core, ServerConfig(**server_settings), outputs=(output,))
    periodic = {}
    specifications = {}
    state_path = Path(config['labStatePath']) if config.get('labStatePath') else None

    def save():
        if state_path is None:
            return
        state = {'devices': [{'id': d.device_id, 'type': d.device_type,
            'sensors': [vars(sensor) for sensor in d.list_sensors()]} for d in core.devices.values()],
            'periodic': list(specifications.values())}
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state))
        temporary.replace(state_path)

    def emit(device, sensor, value):
        observation = core.create_observation(device, sensor, value)
        core.ingest(observation)
        print(json.dumps({'observation': {'device': device, 'sensor': sensor, 'value': value}}), flush=True)

    async def series(command):
        try:
            values = command['values']
            index = 0
            while True:
                emit(command['device'], command['sensor'], values[index % len(values)])
                index += 1
                await asyncio.sleep(command['interval'])
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(json.dumps({'error': str(error)}), flush=True)

    async def command(body):
        action = body['action']
        device_id, sensor_id = body.get('device'), body.get('sensor')
        key = (device_id, sensor_id)
        if action == 'add':
            if not device_id or not sensor_id:
                raise ValueError('Introduce dispositivo y sensor')
            device = core.get_device(device_id)
            if device is None:
                device = Device(device_id, body.get('deviceType', 'sensor'))
                core.register_device(device)
            device.add_sensor(Sensor(sensor_id=sensor_id, observable_property=body.get('property', 'temperature'),
                procedure='lab', feature_of_interest=body.get('feature', 'lab'), unit=body.get('unit', '')))
        elif action == 'emit':
            emit(device_id, sensor_id, body['value'])
        elif action == 'periodic':
            if not isinstance(body['values'], list) or not body['values']:
                raise ValueError('La serie debe ser una lista JSON con valores')
            interval = float(body['interval'])
            import math
            if not math.isfinite(interval) or interval < .1:
                raise ValueError('Intervalo mínimo: 0.1 segundos')
            body['interval'] = interval
            core.create_observation(device_id, sensor_id, body['values'][0])
            if key in periodic:
                periodic.pop(key).cancel()
            specifications[key] = body
            periodic[key] = asyncio.create_task(series(body))
        elif action == 'stop':
            specifications.pop(key, None)
            task = periodic.pop(key, None)
            if task:
                task.cancel()
        elif action in ('remove_sensor', 'remove_device'):
            for existing in list(periodic):
                if existing == key or (action == 'remove_device' and existing[0] == device_id):
                    periodic.pop(existing).cancel()
                    specifications.pop(existing, None)
            if action == 'remove_device':
                core.remove_device(device_id)
            else:
                core.get_device(device_id).remove_sensor(sensor_id)
        elif action != 'list':
            raise ValueError('Acción desconocida')
        save()
        result = {'devices': [
            {'device': device.device_id, 'sensors': [s.sensor_id for s in device.list_sensors()]}
            for device in core.devices.values()]}
        print(json.dumps(result), flush=True)
        return result

    if state_path and state_path.exists():
        state = json.loads(state_path.read_text())
        for saved in state.get('devices', []):
            device = Device(saved['id'], saved['type'])
            for sensor in saved['sensors']:
                device.add_sensor(Sensor(**sensor))
            core.register_device(device)
        for body in state.get('periodic', []):
            key = (body['device'], body['sensor'])
            specifications[key] = body
            periodic[key] = asyncio.create_task(series(body))

    http_control = '--http' in sys.argv
    if http_control:
        from aiohttp import web
        async def receive(request):
            try:
                return web.json_response(await command(await request.json()))
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                return web.json_response({'error': str(error)}, status=400)
        server.app.router.add_post('/_lab/command', receive)

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    def read():
        line = sys.stdin.readline()
        queue.put_nowait(line or None)
    if not http_control:
        loop.add_reader(sys.stdin, read)
    try:
        await server.start()
        print('Reader listo en puerto ' + str(config['server']['port']), flush=True)
        if http_control:
            await asyncio.Future()
        while True:
            line = await queue.get()
            if line is None:
                break
            try:
                await command(json.loads(line))
            except Exception as error:
                print(json.dumps({'error': str(error)}), flush=True)
    finally:
        if not http_control:
            loop.remove_reader(sys.stdin)
        for task in periodic.values():
            task.cancel()
        await asyncio.gather(*periodic.values(), return_exceptions=True)
        await server.stop()


if __name__ == '__main__':
    asyncio.run(run(sys.argv[1]))
