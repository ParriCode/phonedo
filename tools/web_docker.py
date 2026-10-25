"""Contenedores del operador: imágenes configurables y recursos etiquetados."""
import asyncio
import copy
import json
import os
import re
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTS = {'reader': 3002, 'manager': 3003, 'verifier': 5000, 'storage': 5000, 'publisher': 3005}
MASK = '••••••'
NETWORK = 'phonendo-web'


def redact(value):
    if isinstance(value, dict):
        return {key: MASK if any(word in key.lower() for word in ('token', 'password', 'secret', 'seed')) and item
                else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def restore(value, previous):
    if value == MASK:
        return previous
    if isinstance(value, dict):
        old = previous if isinstance(previous, dict) else {}
        return {key: restore(item, old.get(key)) for key, item in value.items()}
    if isinstance(value, list):
        old = previous if isinstance(previous, list) else []
        return [restore(item, old[i] if i < len(old) else None) for i, item in enumerate(value)]
    return value


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.chmod(0o600)
    temporary.replace(path)


class DockerController:
    def __init__(self, client, directory=None):
        self.client = client
        self.directory = Path(directory or os.getenv('PHONENDO_WEB_DOCKER_DIR', str(ROOT / '.run/web-docker'))).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.index = self.directory / 'registry.json'
        self.records = json.loads(self.index.read_text()) if self.index.exists() else {}
        self.credentials_path = self.directory / 'credentials.json'
        if self.credentials_path.exists():
            self.credentials = json.loads(self.credentials_path.read_text())
        else:
            self.credentials = {key: secrets.token_hex(24) for key in
                                ('API_TOKEN_MANAGER', 'API_TOKEN_VERIFIER', 'API_TOKEN_STORAGE', 'MANAGER_PASSWORD')}
            save_json(self.credentials_path, self.credentials)
        self.lock = asyncio.Lock()

    async def run(self, *args, timeout=30):
        def execute():
            try:
                result = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True, timeout=timeout)
            except FileNotFoundError:
                raise ValueError('Falta Docker: instala Docker Engine o Docker Desktop y arráncalo')
            except subprocess.TimeoutExpired:
                raise ValueError('Docker superó el tiempo de espera')
            if result.returncode:
                # No mostramos errores con variables/configuración que puedan contener secretos.
                raise ValueError('Docker no pudo completar ' + str(args[0]) + '. Comprueba el daemon, permisos, imagen y puerto.')
            return (result.stdout + (result.stderr if args[0] == 'logs' else '')).strip()
        return await asyncio.to_thread(execute)

    def persist(self):
        save_json(self.index, self.records)

    def record(self, identifier):
        if identifier not in self.records:
            raise ValueError('Contenedor no gestionado por este panel')
        return self.records[identifier]

    async def inspect(self, record):
        info = json.loads(await self.run('inspect', record['container']))[0]
        labels = info.get('Config', {}).get('Labels', {}) or {}
        if labels.get('phonendo.web.id') != record['id'] or labels.get('phonendo.web.managed') != 'true':
            raise ValueError('El contenedor no pertenece a este panel')
        return info

    async def network(self):
        await self.run('info', '--format', '{{.ServerVersion}}')
        existing = await self.run('network', 'ls', '--filter', 'name=^' + NETWORK + '$', '--format', '{{.Name}}')
        if not existing:
            await self.run('network', 'create', '--label', 'phonendo.web.managed=true', NETWORK)
        else:
            info = json.loads(await self.run('network', 'inspect', NETWORK))[0]
            if (info.get('Labels') or {}).get('phonendo.web.managed') != 'true':
                raise ValueError('Ya existe una red phonendo-web ajena al panel')

    async def deploy(self, body, progress=lambda _: None):
        async with self.lock:
            kind = body['kind']
            if kind not in PORTS:
                raise ValueError('Tipo de servicio desconocido')
            identifier = body['id']
            alias = body['name']
            if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', identifier):
                raise ValueError('Identificador inválido')
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', alias):
                raise ValueError('Nombre Docker: letras minúsculas, números y guiones')
            if identifier in self.records or any(item['name'] == alias for item in self.records.values()):
                raise ValueError('Ya existe un contenedor con esa identidad o nombre')
            image = body.get('image') or f'phonendo-web-{kind}:local'
            if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._/:@-]{0,220}', image):
                raise ValueError('Referencia de imagen inválida')
            port = body.get('port', 0)
            internal = body.get('containerPort', PORTS[kind])
            if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
                raise ValueError('Puerto local inválido (0 = automático)')
            if isinstance(internal, bool) or not isinstance(internal, int) or not 1 <= internal <= 65535:
                raise ValueError('Puerto interno inválido')
            config = copy.deepcopy(body.get('config', {}))
            if not isinstance(config, dict):
                raise ValueError('La configuración debe ser un objeto JSON')
            config.setdefault('server', {}).update(host='0.0.0.0', port=internal)
            if kind == 'reader':
                config['server']['enabled'] = True
                config.setdefault('readerId', alias)
                config['webSettings'] = config.get('webSettings') or {
                    'readerId': config['readerId'], 'token': config['server'].get('token', ''),
                    'httpEnabled': True, 'streamEnabled': config.get('stream', {}).get('enabled', True),
                    'queueSize': 256, 'allowNewDevices': True, 'allowNewSensors': True,
                    'managers': config.get('services', {}).get('managers', [])}
            if kind == 'manager':
                config.setdefault('managerId', alias)
            if kind == 'verifier':
                config['keyPath'] = '/data/signing-key.json'
            if kind == 'publisher':
                config['circuitsPath'] = '/circuits'
            required = {'reader': ('API_TOKEN_MANAGER',),
                        'manager': tuple(self.credentials),
                        'verifier': ('API_TOKEN_VERIFIER', 'MANAGER_PASSWORD'),
                        'storage': ('API_TOKEN_STORAGE',), 'publisher': ('API_TOKEN_MANAGER',)}
            environment = {**{key: self.credentials[key] for key in required[kind]}, **body.get('environment', {})}
            for key, value in environment.items():
                if not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or not isinstance(value, str):
                    raise ValueError('Las variables de entorno deben tener nombre válido y valor de texto')
            if kind == 'reader':
                if config['readerId'] != config['webSettings']['readerId']:
                    raise ValueError('readerId y webSettings.readerId deben coincidir')
                if any(item['kind'] == 'reader' and item['config'].get('readerId') == config['readerId'] for item in self.records.values()):
                    raise ValueError('Ya existe un Reader con esa identidad')
                managers = config['webSettings']['managers']
                for target in managers:
                    if isinstance(target, str):
                        raise ValueError('Reader: cada Manager necesita un objeto url/token')
                    if not target.get('token'):
                        target['token'] = environment['API_TOKEN_MANAGER']
            await self.network()
            progress('Preparando imagen Docker')
            if body.get('build', False):
                if kind == 'publisher':
                    await self.run('build', '-t', image, '-f', ROOT / 'apps/publisher/Dockerfile', ROOT, timeout=900)
                else:
                    await self.run('build', '-t', image, ROOT / 'apps' / kind, timeout=900)
            else:
                try:
                    await self.run('image', 'inspect', image)
                except ValueError:
                    progress('Descargando imagen Docker')
                    await self.run('pull', image, timeout=900)
            folder = self.directory / identifier
            folder.mkdir(mode=0o700)
            (folder / 'data').mkdir(mode=0o700)
            control = secrets.token_hex(32)
            record = {'id': identifier, 'kind': kind, 'name': alias, 'container': f'phonendo-web-{identifier}',
                      'image': image, 'containerPort': internal, 'config': config,
                      'environment': environment, 'control': control, 'stellarIdentity': bool(body.get('stellarIdentity'))}
            save_json(folder / 'config/config.json', config)
            args = ['run', '-d', '--name', record['container'], '--network', NETWORK, '--network-alias', alias,
                    '--label', 'phonendo.web.managed=true', '--label', 'phonendo.web.id=' + identifier,
                    '--restart', 'unless-stopped', '-p', f'127.0.0.1:{port if port else ""}:{internal}',
                    '--mount', f'type=bind,src={folder / "config"},dst=/phonendo-config,readonly',
                    '--mount', f'type=bind,src={folder / "data"},dst=/data',
                    '--add-host', 'host.docker.internal:host-gateway',
                    '-e', f'{kind.upper()}_CONFIG_PATH=/phonendo-config/config.json',
                    '-e', f'PORT_{kind.upper()}={internal}', '-e', 'PHONENDO_VERBOSE=true',
                    '-e', 'PHONENDO_LOGS_DIR=/data/logs', '-e', 'PHONENDO_DB_PATH=/data/phonendo']
            for key, value in environment.items():
                args.extend(['-e', key + '=' + value])
            if kind == 'reader':
                args.extend(['--mount', f'type=bind,src={ROOT / "tools/web_runtime.py"},dst=/opt/phonendo/tools/web_runtime.py,readonly',
                             '-e', 'PHONENDO_READER_ROOT=/app/reader', '-e', 'PHONENDO_WEB_READER_MODE=1',
                             '-e', 'PHONENDO_WEB_READER_ID=' + identifier, '-e', 'WEB_CONTROL_TOKEN=' + control])
            if kind == 'publisher':
                (ROOT / 'circuits/build').mkdir(exist_ok=True)
                args.extend(['--mount', f'type=bind,src={ROOT / "circuits/scripts"},dst=/circuits/scripts,readonly',
                             '--mount', f'type=bind,src={ROOT / "circuits/build"},dst=/circuits/build'])
                if record['stellarIdentity']:
                    identity = Path(os.getenv('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'stellar'
                    if not identity.is_dir():
                        raise ValueError('No existe la configuración local de Stellar')
                    args.extend(['--mount', f'type=bind,src={identity},dst=/root/.config/stellar,readonly'])
            args.append(image)
            if kind == 'reader':
                args.extend(['python', '/opt/phonendo/tools/web_runtime.py'])
            if kind == 'verifier':
                # Clave persistente dentro del volumen de esta instancia, nunca en la imagen.
                code = ("import base64,json,runpy; from pathlib import Path; "
                        "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; "
                        "p=Path('/data/signing-key.json'); "
                        "p.exists() or p.write_text(json.dumps({'d':base64.urlsafe_b64encode(Ed25519PrivateKey.generate().private_bytes_raw()).decode().rstrip('=')})); "
                        "p.chmod(0o600); runpy.run_path('/app/verifier/verifier.py',run_name='__main__')")
                args.extend(['python', '-c', code])
            progress('Arrancando contenedor')
            try:
                await self.run(*args)
                info = await self.inspect(record)
                binding = info['NetworkSettings']['Ports'][f'{internal}/tcp'][0]
                record['url'] = 'http://127.0.0.1:' + binding['HostPort']
                record['dockerUrl'] = f'http://{alias}:{internal}'
                self.records[identifier] = record
                self.persist()
                progress('Esperando a que responda el servicio')
                for _ in range(40):
                    try:
                        return await self.snapshot(identifier, require_ready=True)
                    except (ValueError, OSError, asyncio.TimeoutError):
                        await asyncio.sleep(.5)
                result = await self.snapshot(identifier)
                result['error'] = 'El contenedor se creó pero no responde todavía; consulta sus logs'
                return result
            except Exception:
                # No se toca ningún contenedor salvo el recién creado y con nuestras etiquetas.
                try:
                    await self.inspect(record)
                    await self.run('rm', '-f', record['container'])
                except ValueError:
                    pass
                self.records.pop(identifier, None)
                self.persist()
                raise

    async def reader_request(self, record, method='GET', body=None):
        token = record['config'].get('webSettings', {}).get('token', record['config'].get('server', {}).get('token', ''))
        headers = {'X-Phonendo-Control-Token': record['control'], 'Authorization': 'Bearer ' + token}
        from aiohttp import ClientTimeout
        async with self.client.request(method, record['url'] + '/_web/reader', headers=headers, json=body,
                                       timeout=ClientTimeout(total=30),
                                       allow_redirects=False) as response:
            if response.status != 200:
                if response.status == 400:
                    reply = await response.json()
                    raise ValueError(reply.get('error', 'Acción rechazada por el Reader'))
                raise ValueError('El control del Reader no responde. Consulta los logs del contenedor.')
            return await response.json()

    async def snapshot(self, identifier, require_ready=False):
        record = self.record(identifier)
        info = await self.inspect(record)
        result = {'id': identifier, 'kind': record['kind'], 'name': record['name'],
                  'container': record['container'], 'image': record['image'], 'url': record['url'],
                  'dockerUrl': record['dockerUrl'], 'state': info['State']['Status'],
                  'serviceConfig': redact(record['config']), 'environment': {key: MASK for key in record['environment']},
                  'devices': [], 'events': []}
        if result['state'] == 'running' and record['kind'] == 'reader':
            try:
                result.update(await self.reader_request(record))
                result['url'] = record['url']
            except (ValueError, OSError, asyncio.TimeoutError):
                if require_ready:
                    raise ValueError('Esperando al Reader')
                result['error'] = 'Reader arrancando o sin respuesta; consulta los logs Docker'
        elif require_ready:
            if result['state'] != 'running':
                raise ValueError('El contenedor está detenido')
            async with self.client.get(record['url'] + '/', allow_redirects=False) as response:
                if response.status != 200:
                    raise ValueError('Servicio sin respuesta')
        return result

    async def logs(self, identifier):
        record = self.record(identifier)
        await self.inspect(record)
        output = await self.run('logs', '--tail', '150', record['container'])
        def secret_values(value):
            result = []
            if isinstance(value, dict):
                for key, item in value.items():
                    if any(word in key.lower() for word in ('token', 'password', 'secret', 'seed')) and isinstance(item, str):
                        result.append(item)
                    else:
                        result.extend(secret_values(item))
            elif isinstance(value, list):
                for item in value:
                    result.extend(secret_values(item))
            return result
        for value in list(record['environment'].values()) + [record['control']] + secret_values(record['config']):
            if value:
                output = output.replace(value, '[oculto]')
        return output[-100000:].splitlines()

    async def action(self, identifier, body):
        async with self.lock:
            record = self.record(identifier)
            await self.inspect(record)
            action = body['action']
            if action in ('start', 'stop', 'restart'):
                args = ['stop', '--time', '5'] if action == 'stop' else [action]
                await self.run(*args, record['container'], timeout=60)
            elif action == 'remove':
                await self.run('rm', '-f', record['container'])
                del self.records[identifier]
                self.persist()
                return {'removed': True, 'dataRetained': True}
            elif action == 'config':
                config = restore(body['config'], record['config'])
                config.setdefault('server', {}).update(host='0.0.0.0', port=record['containerPort'])
                if record['kind'] == 'reader':
                    raise ValueError('Usa los controles en directo del Reader')
                if record['kind'] == 'verifier':
                    config['keyPath'] = '/data/signing-key.json'
                if record['kind'] == 'publisher':
                    config['circuitsPath'] = '/circuits'
                record['config'] = config
                save_json(self.directory / identifier / 'config/config.json', config)
                self.persist()
                await self.run('restart', record['container'], timeout=60)
            else:
                raise ValueError('Acción Docker desconocida')
            return await self.snapshot(identifier)

    async def reader_action(self, identifier, body):
        async with self.lock:
            record = self.record(identifier)
            await self.inspect(record)
            if record['kind'] != 'reader':
                raise ValueError('El contenedor no es un Reader')
            snapshot = await self.reader_request(record, 'POST', body)
            if body.get('action') == 'config':
                previous = record['config'].get('webSettings', {})
                settings = copy.deepcopy(body['config'])
                if not settings.get('token') and not body.get('clearToken'):
                    settings['token'] = previous.get('token', '')
                for target in settings.get('managers', []):
                    old = next((item for item in previous.get('managers', []) if item['url'] == target['url']), {})
                    if not target.get('token'):
                        target['token'] = old.get('token', '')
                record['config']['webSettings'] = settings
                record['config']['readerId'] = settings['readerId']
                record['config']['stream'] = {'enabled': settings['streamEnabled']}
                record['config'].setdefault('server', {})['token'] = settings['token']
                record['config']['services'] = {'managers': settings['managers'] if settings['httpEnabled'] else []}
                save_json(self.directory / identifier / 'config/config.json', record['config'])
                self.persist()
            snapshot.update({key: record[key] for key in ('container', 'image', 'dockerUrl', 'url')})
            snapshot['state'] = 'running'
            return snapshot
