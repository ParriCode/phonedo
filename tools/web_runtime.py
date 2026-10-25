#!/usr/bin/env python3
"""Panel local: Readers reales en memoria y consulta de servicios Phonendo."""
import asyncio
import ipaddress
import hmac
import json
import math
import os
import re
import subprocess
import sys
from collections import deque
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import ClientSession, ClientTimeout, ClientError, web

ROOT = Path(__file__).resolve().parents[1]
READER_ROOT = Path(os.getenv('PHONENDO_READER_ROOT', str(ROOT / 'apps/reader')))
sys.path[:0] = [str(READER_ROOT / 'python/core'), str(READER_ROOT / 'python/server'), str(ROOT / 'tools')]
from reader_core import ReaderCore, Device, Sensor
from reader_server import ReaderServer, ServerConfig
from reader_server.serialization import observation_event


def local_url(value):
    """El puente solo alcanza servicios locales o de la LAN, nunca URLs arbitrarias."""
    url = urlsplit(value)
    if url.scheme not in ('http', 'https') or url.username or url.password or url.query or url.fragment:
        raise ValueError('URL de servicio inválida')
    host = url.hostname or ''
    if host != 'localhost':
        if os.getenv('PHONENDO_WEB_READER_MODE') == '1' and re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.-]*', host):
            return value.rstrip('/')
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError('Usa localhost o la IP privada del servicio')
        if not (address.is_private or address.is_loopback) or address.is_unspecified:
            raise ValueError('Solo se permiten servicios locales o de la LAN')
    return value.rstrip('/')


def name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError('Identificador vacío o demasiado largo')
    return value.strip()


class PushOutput:
    def __init__(self, runtime):
        self.runtime = runtime

    @property
    def managers(self):
        return self.runtime.settings['managers'] if self.runtime.settings['httpEnabled'] else []

    def publish(self, reader_id, observation):
        runtime = self.runtime
        event = observation_event(reader_id, observation)
        runtime.log('observation_created', observationId=observation.observation_id,
                    deviceId=observation.device_id, sensorId=observation.sensor_id, value=observation.simple_result)
        if runtime.settings['httpEnabled']:
            for target in runtime.settings['managers']:
                runtime.spawn(runtime.deliver(dict(target), event))


class ManagedReader:
    def __init__(self, session, identifier, config):
        self.session, self.id = session, identifier
        self.events = deque(maxlen=200)
        self.sequence = 0
        self.boot_id = os.urandom(12).hex()
        self.tasks = set()
        self.settings = self.validate(config)
        core = ReaderCore(self.settings['readerId'])
        container = os.getenv('PHONENDO_WEB_READER_MODE') == '1'
        self.state_path = Path('/data/reader-state.json') if container else None
        self.server = ReaderServer(core, ServerConfig(enabled=True, host='0.0.0.0' if container else '127.0.0.1',
                                                     port=int(os.getenv('PORT_READER', '3002')) if container else 0),
                                   outputs=(PushOutput(self),))

    @staticmethod
    def validate(config):
        targets = []
        for target in config.get('managers', []):
            targets.append({'url': local_url(target['url']), 'token': str(target.get('token', ''))})
        if len(targets) > 20:
            raise ValueError('Máximo 20 Managers por Reader')
        queue_size = config.get('queueSize', 256)
        if isinstance(queue_size, bool) or not isinstance(queue_size, int) or not 1 <= queue_size <= 4096:
            raise ValueError('La cola SSE debe contener entre 1 y 4096 eventos')
        return {'readerId': name(config['readerId']), 'streamEnabled': bool(config.get('streamEnabled', True)),
                'queueSize': queue_size,
                'httpEnabled': bool(config.get('httpEnabled', True)), 'token': str(config.get('token', '')),
                'allowNewDevices': bool(config.get('allowNewDevices', True)),
                'allowNewSensors': bool(config.get('allowNewSensors', True)), 'managers': targets}

    def log(self, message, **fields):
        self.sequence += 1
        self.events.append({'sequence': self.sequence, 'message': message, **fields})
        if os.getenv('PHONENDO_WEB_READER_MODE') == '1':
            print(json.dumps({'sequence': self.sequence, 'message': message, **fields}), flush=True)

    def spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def deliver(self, target, event):
        try:
            async with self.session.post(target['url'] + '/newEvent',
                    json={**event, 'token': target['token']}, allow_redirects=False) as response:
                self.log('manager_http_accepted' if response.status in (200, 202, 207) else 'manager_http_rejected',
                         observationId=event['observationId'], peer=target['url'], status=response.status)
                if response.status in (200, 207):
                    reply = await response.json(content_type=None)
                    results = reply.get('results', [{'result': reply}])
                    for result in results:
                        if result.get('result', {}).get('status') == 'Verified':
                            self.log('manager_reports_verified', observationId=event['observationId'],
                                     eventId=result['result'].get('eventId'), peer=target['url'])
        except Exception:
            self.log('manager_http_unreachable', observationId=event['observationId'], peer=target['url'])

    async def start(self):
        await self.server.start()
        self.url = 'http://127.0.0.1:' + str(self.server.runner.addresses[0][1])
        self.apply(self.settings)
        self.log('reader_started')

    def apply(self, config):
        settings = self.validate(config)
        if settings['readerId'] != self.server.core.reader_id:
            raise ValueError('readerId es estable; crea otro Reader para cambiarlo')
        if settings['httpEnabled'] and settings['streamEnabled'] and settings['managers']:
            # Los Managers conservan la responsabilidad de rechazar conexiones redundantes.
            self.log('reader_both_transports_enabled')
        old_stream = self.server.config.stream_enabled
        token_changed = self.server.config.token != settings['token']
        queue_changed = self.server.config.queue_size != settings['queueSize']
        self.server.config = replace(self.server.config, token=settings['token'], stream_enabled=settings['streamEnabled'], queue_size=settings['queueSize'])
        self.server.core.allow_new_devices = settings['allowNewDevices']
        self.server.core.allow_new_sensors = settings['allowNewSensors']
        if (old_stream and not settings['streamEnabled']) or token_changed or queue_changed:
            self.server.stream.close()
        self.server.stream.queue_size = settings['queueSize']
        self.settings = settings
        self.log('reader_configuration_applied')

    def snapshot(self):
        return {'id': self.id, 'url': self.url, 'bootId': self.boot_id,
                'config': {**self.settings, 'token': '', 'managers': [
                    {**target, 'token': ''} for target in self.settings['managers']]},
                'devices': [{'id': device.device_id, 'type': device.device_type,
                    'sensors': [{'id': sensor.sensor_id, 'property': sensor.observable_property,
                                 'unit': sensor.unit, 'procedure': sensor.procedure,
                                 'featureOfInterest': sensor.feature_of_interest}
                                for sensor in device.list_sensors()]}
                            for device in self.server.core.devices.values()], 'events': list(self.events)}

    def save(self):
        if self.state_path is None:
            return
        snapshot = self.snapshot()
        temporary = self.state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'settings': self.settings, 'devices': snapshot['devices']}))
        temporary.chmod(0o600)
        temporary.replace(self.state_path)

    def restore_devices(self):
        if self.state_path is None or not self.state_path.is_file():
            return
        saved = json.loads(self.state_path.read_text())
        for item in saved.get('devices', []):
            device = Device(item['id'], item['type'])
            for sensor in item['sensors']:
                device.add_sensor(Sensor(sensor['property'], sensor['procedure'], sensor['featureOfInterest'],
                                         sensor['id'], sensor.get('unit')))
            self.server.core.add_device(device)

    async def close(self):
        for task in tuple(self.tasks):
            task.cancel()
        await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
        await self.server.stop()


@web.middleware
async def local_control(request, handler):
    if request.path.startswith('/api/'):
        origin = request.headers.get('Origin')
        if origin and origin != f'{request.scheme}://{request.host}':
            raise web.HTTPForbidden(text='Origen no permitido')
        if request.method != 'GET' and request.headers.get('X-Phonendo-Control') != 'local':
            raise web.HTTPForbidden(text='Cabecera de control requerida')
    try:
        return await handler(request)
    except (ValueError, KeyError, TypeError) as error:
        return web.json_response({'error': str(error)}, status=400)
    except (OSError, ClientError, asyncio.TimeoutError):
        return web.json_response({'error': 'Servicio Docker o Reader sin respuesta'}, status=502)


async def reader_action(request):
    runtime = request.app['readers'].get(request.match_info.get('identifier', os.getenv('PHONENDO_WEB_READER_ID', '')))
    if runtime is None:
        return web.json_response({'error': 'Reader no gestionado o sesión terminada'}, status=404)
    if request.method == 'GET':
        return web.json_response(runtime.snapshot())
    if request.method == 'DELETE':
        await runtime.close()
        del request.app['readers'][runtime.id]
        return web.json_response({'stopped': True})
    body = await request.json()
    action = body['action']
    if action == 'config':
        config = body['config']
        # Los secretos no se devuelven al navegador; vacío conserva el anterior.
        if not config.get('token') and not body.get('clearToken'):
            config['token'] = runtime.settings['token']
        for target in config.get('managers', []):
            previous = next((item for item in runtime.settings['managers'] if item['url'] == target['url']), None)
            if previous and not target.get('token'):
                target['token'] = previous['token']
        runtime.apply(config)
    elif action == 'device':
        runtime.server.core.add_device(Device(name(body['deviceId']), body.get('deviceType', 'device')))
        runtime.log('device_added', deviceId=body['deviceId'])
    elif action == 'sensor':
        device = runtime.server.core.get_device(name(body['deviceId']))
        if device is None:
            raise ValueError('Dispositivo desconocido')
        device.add_sensor(Sensor(name(body['property']), body.get('procedure', 'manual'),
                                body.get('featureOfInterest', device.device_id), name(body['sensorId']), body.get('unit')))
        runtime.log('sensor_added', deviceId=device.device_id, sensorId=body['sensorId'])
    elif action == 'pulse':
        value = body['value']
        count = body.get('count', 1)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Valor numérico finito requerido')
        if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 32:
            raise ValueError('Entre 1 y 32 lecturas por emisión')
        device = runtime.server.core.get_device(name(body['deviceId']))
        if device is None:
            raise ValueError('Dispositivo desconocido')
        sensor = device.get_sensor(name(body['sensorId']))
        if sensor.procedure != 'manual-pulse':
            raise ValueError('Este sensor no admite emisión manual')
        for _ in range(count):
            runtime.server.service.ingest(runtime.server.core.create_observation(device.device_id, sensor.sensor_id, value))
    elif action == 'remove-device':
        runtime.server.core.remove_device(name(body['deviceId']))
        runtime.log('device_removed', deviceId=body['deviceId'])
    elif action == 'remove-sensor':
        device = runtime.server.core.get_device(name(body['deviceId']))
        if device is None:
            raise ValueError('Dispositivo desconocido')
        device.remove_sensor(name(body['sensorId']))
        runtime.log('sensor_removed', sensorId=body['sensorId'])
    else:
        raise ValueError('Acción desconocida')
    runtime.save()
    return web.json_response(runtime.snapshot())


async def probe(request):
    body = await request.json()
    base = local_url(body['url'])
    path = body.get('path', '/logs')
    if path not in ('/', '/health', '/info', '/logs', '/devices', '/metadata', '/raw'):
        raise ValueError('Ruta no permitida')
    headers = {'Authorization': 'Bearer ' + body['token']} if body.get('token') else {}
    try:
        async with request.app['client'].get(base + path, headers=headers, allow_redirects=False) as response:
            raw = await response.content.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Respuesta demasiado grande')
            if response.status != 200:
                return web.json_response({'error': f'El servicio respondió HTTP {response.status}'}, status=502)
            try:
                data = json.loads(raw)
            except ValueError:
                data = {'message': 'Servicio accesible'}
            return web.json_response(data)
    except (OSError, asyncio.TimeoutError):
        return web.json_response({'error': 'Servicio sin respuesta'}, status=502)


async def resources(app):
    async with ClientSession(timeout=ClientTimeout(total=5), trust_env=False) as session:
        app['client'] = session
        from web_docker import DockerController
        app['docker'] = DockerController(session)
        yield
        await asyncio.gather(*tuple(app['operation_tasks']), return_exceptions=True)


async def docker_list(request):
    result = []
    for identifier in tuple(request.app['docker'].records):
        try:
            result.append(await request.app['docker'].snapshot(identifier))
        except (ValueError, OSError, ClientError, asyncio.TimeoutError):
            pass
    return web.json_response(result)


def enqueue(app, coroutine_factory):
    import uuid
    identifier = uuid.uuid4().hex
    operation = {'id': identifier, 'state': 'running', 'message': 'Preparando operación Docker'}
    app['operations'][identifier] = operation
    async def run():
        try:
            operation['result'] = await coroutine_factory(lambda message: operation.update(message=message))
            operation.update(state='succeeded', message='Operación completada')
        except Exception as error:
            operation.update(state='failed', error=str(error))
    task = asyncio.create_task(run())
    app['operation_tasks'].add(task)
    task.add_done_callback(app['operation_tasks'].discard)
    return web.json_response(operation, status=202)


async def docker_create(request):
    body = await request.json()
    return enqueue(request.app, lambda progress: request.app['docker'].deploy(body, progress))


async def docker_operation(request):
    operation = request.app['operations'].get(request.match_info['identifier'])
    if operation is None:
        raise web.HTTPNotFound()
    return web.json_response(operation)


async def docker_item(request):
    identifier = request.match_info['identifier']
    controller = request.app['docker']
    if request.method == 'GET':
        return web.json_response(await controller.snapshot(identifier))
    body = await request.json()
    return enqueue(request.app, lambda _: controller.action(identifier, body))


async def docker_logs(request):
    return web.json_response(await request.app['docker'].logs(request.match_info['identifier']))


async def docker_reader(request):
    controller = request.app['docker']
    identifier = request.match_info['identifier']
    if request.method == 'GET':
        return web.json_response(await controller.snapshot(identifier))
    if request.method == 'DELETE':
        return web.json_response(await controller.action(identifier, {'action': 'remove'}))
    return web.json_response(await controller.reader_action(identifier, await request.json()))


async def launch(app):
    if os.getenv('PHONENDO_WEB_NO_BROWSER') == '1':
        return
    port = int(os.getenv('WEB_PORT', '8080'))
    config = json.loads(Path(os.getenv('PUBLISHER_CONFIG_PATH', str(ROOT / 'apps/publisher/config.json'))).read_text())
    contracts = sorted(value for value in config.get('contracts', {}).values()
                       if isinstance(value, str) and re.fullmatch(r'C[A-Z2-7]{55}', value))
    explorer = 'https://stellar.expert/explorer/testnet' + ('/contract/' + contracts[0] if contracts else '')
    async def open_when_ready():
        local = f'http://127.0.0.1:{port}/operator.html'
        for _ in range(30):
            try:
                async with app['client'].get(local) as response:
                    if response.status == 200:
                        break
            except OSError:
                pass
            await asyncio.sleep(.1)
        for url in (local, explorer):
            try:
                opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                await asyncio.wait_for(asyncio.to_thread(subprocess.run, [opener, url], capture_output=True), 15)
            except (OSError, asyncio.TimeoutError):
                print('Abre en tu navegador: ' + url, flush=True)
    app['opener'] = asyncio.create_task(open_when_ready())


def create_app():
    app = web.Application(middlewares=[local_control], client_max_size=65536)
    app['operations'] = {}
    app['operation_tasks'] = set()
    app.cleanup_ctx.append(resources)
    app.on_startup.append(launch)
    app.router.add_get('/api/local/containers', docker_list)
    app.router.add_post('/api/local/containers', docker_create)
    app.router.add_route('*', '/api/local/containers/{identifier}', docker_item)
    app.router.add_get('/api/local/containers/{identifier}/logs', docker_logs)
    app.router.add_get('/api/local/operations/{identifier}', docker_operation)
    app.router.add_route('*', '/api/local/readers/{identifier}', docker_reader)
    app.router.add_post('/api/local/probe', probe)
    async def static(request):
        path = (ROOT / 'apps/web' / (request.match_info['file'] or 'index.html')).resolve()
        if not path.is_relative_to(ROOT / 'apps/web') or not path.is_file():
            raise web.HTTPNotFound()
        # Respuesta directa: evita el HTML antiguo cacheado en el mismo puerto.
        import mimetypes
        return web.Response(body=path.read_bytes(), content_type=mimetypes.guess_type(str(path))[0] or 'application/octet-stream',
                            headers={'Cache-Control': 'no-store'})
    app.router.add_get('/{file:.*}', static)
    return app


async def container_reader():
    config = json.loads(Path(os.getenv('READER_CONFIG_PATH', '/phonendo-config/config.json')).read_text())
    settings = config['webSettings']
    async with ClientSession(timeout=ClientTimeout(total=10), trust_env=False) as session:
        runtime = ManagedReader(session, os.environ['PHONENDO_WEB_READER_ID'], settings)
        @web.middleware
        async def control(request, handler):
            if request.path.startswith('/_web/') and not hmac.compare_digest(
                    request.headers.get('X-Phonendo-Control-Token', ''), os.environ['WEB_CONTROL_TOKEN']):
                raise web.HTTPForbidden()
            try:
                return await handler(request)
            except (ValueError, KeyError, TypeError) as error:
                return web.json_response({'error': str(error)}, status=400)
        runtime.server.app.middlewares.insert(0, control)
        runtime.server.app['readers'] = {runtime.id: runtime}
        runtime.server.app.router.add_get('/_web/reader', reader_action)
        runtime.server.app.router.add_post('/_web/reader', reader_action)
        runtime.restore_devices()
        await runtime.start()
        runtime.save()
        try:
            await asyncio.Future()
        finally:
            await runtime.close()


if __name__ == '__main__':
    if os.getenv('PHONENDO_WEB_READER_MODE') == '1':
        asyncio.run(container_reader())
    else:
        web.run_app(create_app(), host='127.0.0.1', port=int(os.getenv('WEB_PORT', '8080')))
