"""Contenedores del operador: imágenes configurables y recursos etiquetados."""
import asyncio
import copy
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import keys

ROOT = Path(__file__).resolve().parents[1]
# Dentro del contenedor solo se monta la clave o las carteras de keys/ que necesita.
VERIFIER_KEY = '/keys/verifier.json'
STELLAR_DIR = '/keys/stellar'
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
        return previous if previous is not None else ''
    if isinstance(value, dict):
        old = previous if isinstance(previous, dict) else {}
        return {key: restore(item, old.get(key)) for key, item in value.items()}
    if isinstance(value, list):
        old = previous if isinstance(previous, list) else []
        # Los destinos pueden quitarse o reordenarse desde el formulario visual.
        def original(item, index):
            if isinstance(item, dict) and 'url' in item:
                return next((target for target in old if isinstance(target, dict)
                             and target.get('url') == item['url']), None)
            return old[index] if index < len(old) else None
        return [restore(item, original(item, i)) for i, item in enumerate(value)]
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

    async def compose_snapshot(self, identifier):
        if not identifier.startswith('compose-') or identifier[8:] not in PORTS:
            raise ValueError('Contenedor no gestionado por este panel')
        kind = identifier[8:]
        names = await self.run('ps', '-a', '--filter', 'label=com.docker.compose.project=phonendo',
                               '--filter', 'label=com.docker.compose.service=' + kind, '--format', '{{.ID}}')
        if not names:
            raise ValueError('Contenedor Compose no encontrado')
        info = json.loads(await self.run('inspect', names.splitlines()[0]))[0]
        labels = info.get('Config', {}).get('Labels', {}) or {}
        if labels.get('com.docker.compose.project') != 'phonendo' or labels.get('com.docker.compose.service') != kind:
            raise ValueError('El contenedor no pertenece al proyecto Phonendo')
        ports = info.get('NetworkSettings', {}).get('Ports') or {}
        binding = next((item[0] for item in ports.values() if item), None)
        url = 'http://127.0.0.1:' + binding['HostPort'] if binding else ''
        config = {}
        config_root = (ROOT / 'deploy/docker').resolve()
        for mount in info.get('Mounts', []):
            source = Path(mount.get('Source', '')).resolve()
            if (mount.get('Destination') == f'/app/{kind}/config.json'
                    and source.is_file() and source.is_relative_to(config_root)):
                config = redact(json.loads(source.read_text()))
                break
        return {'id': identifier, 'kind': kind, 'name': info['Name'].lstrip('/'),
                'container': info['Id'], 'image': info['Config']['Image'], 'url': url,
                'dockerUrl': f'http://{kind}:{PORTS[kind]}', 'state': info['State']['Status'],
                'serviceConfig': config, 'environment': {}, 'devices': [], 'events': [], 'compose': True}

    async def compose_snapshots(self):
        await self.run('info', '--format', '{{.ServerVersion}}')
        result = []
        for kind in PORTS:
            try:
                result.append(await self.compose_snapshot('compose-' + kind))
            except ValueError:
                continue
        return result

    async def connection_action(self, body, progress=lambda _: None):
        source_id, target_id = body.get('sourceId'), body.get('targetId')
        transport = body.get('transport')
        if transport not in ('http', 'sse', None):
            raise ValueError('Transporte desconocido')
        async with self.lock:
            source = await self.snapshot(source_id)
            target = await self.snapshot(target_id)
            pair = (source['kind'], target['kind'])
            if pair not in (('reader', 'manager'), ('manager', 'verifier'), ('manager', 'storage'), ('manager', 'publisher')):
                raise ValueError('Estos servicios no admiten una conexión directa')
            if pair == ('manager', 'publisher') and transport == 'http':
                raise ValueError('Publisher solo admite Stream desde Manager')

            def config_path(snapshot):
                if snapshot.get('compose'):
                    path = ROOT / 'deploy/docker' / (snapshot['kind'] + '.json')
                    # El archivo ha de ser exactamente el volumen montado en este contenedor.
                    return path.resolve()
                return self.directory / snapshot['id'] / 'config/config.json'

            changed = {}
            for snapshot in (source, target):
                path = config_path(snapshot)
                if snapshot.get('compose'):
                    info = json.loads(await self.run('inspect', snapshot['container']))[0]
                    mounted = any(Path(item.get('Source', '')).resolve() == path and
                                  item.get('Destination') == f"/app/{snapshot['kind']}/config.json"
                                  for item in info.get('Mounts', []))
                    if not mounted or not path.is_relative_to((ROOT / 'deploy/docker').resolve()):
                        raise ValueError('No se puede editar la configuración de este contenedor Compose')
                changed[snapshot['id']] = (snapshot, path, json.loads(path.read_text()))

            source_config = changed[source_id][2]
            target_config = changed[target_id][2]
            def replace_target(config, section, key, url, item=None):
                values = config.setdefault(section, {}).setdefault(key, [])
                values[:] = [value for value in values if (value.get('url') if isinstance(value, dict) else value) != url]
                if item is not None:
                    values.append(item)

            if pair == ('reader', 'manager'):
                reader, manager = source_config, target_config
                reader_url, manager_url = source['dockerUrl'], target['dockerUrl']
                manager_info = json.loads(await self.run('inspect', target['container']))[0]
                manager_token = next((value.split('=', 1)[1] for value in manager_info['Config'].get('Env', [])
                                      if value.startswith('API_TOKEN_MANAGER=')), '')
                replace_target(reader, 'services', 'managers', manager_url,
                               {'url': manager_url, 'token': manager_token} if transport == 'http' else None)
                reader_token = reader.get('webSettings', {}).get('token') or reader.get('server', {}).get('token', '')
                replace_target(manager, 'subscriptions', 'readers', reader_url,
                               {'url': reader_url, 'token': reader_token} if transport == 'sse' and reader_token else reader_url if transport == 'sse' else None)
                if transport == 'sse':
                    reader.setdefault('stream', {})['enabled'] = True
            elif pair[1] in ('verifier', 'storage'):
                manager, peer = source_config, target_config
                key = 'verifiers' if pair[1] == 'verifier' else 'storages'
                replace_target(manager, 'services', key, target['dockerUrl'], target['dockerUrl'] if transport == 'http' else None)
                replace_target(manager, 'subscriptions', key, target['dockerUrl'], target['dockerUrl'] if transport == 'sse' else None)
                replace_target(peer, 'subscriptions', 'managers', source['dockerUrl'], source['dockerUrl'] if transport == 'sse' else None)
                if transport == 'sse':
                    peer.setdefault('server', {})['publicUrl'] = target['dockerUrl']
                    manager.setdefault('outputStreams', {})[key] = True
            else:
                replace_target(target_config, 'subscriptions', 'managers', source['dockerUrl'],
                               source['dockerUrl'] if transport == 'sse' else None)

            old = {identifier: path.read_bytes() for identifier, (_, path, _) in changed.items()}
            modes = {identifier: path.stat().st_mode & 0o777 for identifier, (_, path, _) in changed.items()}
            try:
                for identifier, (snapshot, path, config) in changed.items():
                    if snapshot.get('compose'):
                        # Compose monta el archivo, así que se conserva su inode.
                        path.write_text(json.dumps(config, indent=2))
                    else:
                        save_json(path, config)
                    path.chmod(modes[identifier])
                for snapshot, _, _ in changed.values():
                    progress('Reiniciando ' + snapshot['name'])
                    await self.run('restart', snapshot['container'], timeout=90)
            except Exception:
                for identifier, (_, path, _) in changed.items():
                    path.write_bytes(old[identifier])
                    path.chmod(modes[identifier])
                for snapshot, _, _ in changed.values():
                    try:
                        await self.run('restart', snapshot['container'], timeout=90)
                    except ValueError:
                        pass
                raise
            return {'sourceId': source_id, 'targetId': target_id, 'transport': transport}

    async def image_snapshots(self):
        await self.run('info', '--format', '{{.ServerVersion}}')
        output = await self.run('image', 'ls', '--format', '{{.Repository}}:{{.Tag}}')
        images = []
        for image in output.splitlines():
            match = re.fullmatch(r'phonendo-(web-)?(reader|manager|verifier|storage|publisher):([a-zA-Z0-9._-]+)', image)
            if not match:
                continue
            source = 'panel' if match[1] else 'compose'
            if source == 'panel' and image != f'phonendo-web-{match[2]}:local':
                continue
            images.append({'id': 'image-' + hashlib.sha256(image.encode()).hexdigest()[:12],
                           'kind': match[2], 'name': image, 'image': image,
                           'imageSource': source, 'imageOnly': True, 'state': 'image'})
        return images

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

    async def image_action(self, kind, action, progress=lambda _: None, source='panel', reference=None):
        if kind not in PORTS:
            raise ValueError('Tipo de servicio desconocido')
        if source == 'compose':
            async with self.lock:
                if action == 'build':
                    progress('Construyendo imagen Docker Compose')
                    await self.run('compose', '-f', ROOT / 'deploy/docker/compose.yml', 'build', kind, timeout=900)
                    return {'image': f'phonendo-{kind}', 'built': True}
                if action == 'remove':
                    if not isinstance(reference, str) or not re.fullmatch(r'phonendo-' + kind + r':[a-zA-Z0-9._-]+', reference):
                        raise ValueError('Imagen Compose no permitida')
                    await self.run('image', 'inspect', reference)
                    await self.run('image', 'rm', reference)
                    return {'image': reference, 'removed': True}
                raise ValueError('Acción de imagen desconocida')
        image = f'phonendo-web-{kind}:local'
        async with self.lock:
            if action == 'build':
                await self.run('info', '--format', '{{.ServerVersion}}')
                try:
                    existing = json.loads(await self.run('image', 'inspect', image))[0]
                except ValueError:
                    existing = None
                if existing:
                    labels = existing.get('Config', {}).get('Labels', {}) or {}
                    owned = labels.get('phonendo.web.managed') == 'true' and labels.get('phonendo.web.kind') == kind
                    legacy = any(record['kind'] == kind and record['image'] == image for record in self.records.values())
                    if not owned and not legacy:
                        raise ValueError('El tag de imagen ya existe y no pertenece a este panel')
                progress('Construyendo imagen Docker')
                args = ['build', '--label', 'phonendo.web.managed=true', '--label', 'phonendo.web.kind=' + kind, '-t', image]
                if kind == 'publisher':
                    args.extend(['-f', ROOT / 'apps/publisher/Dockerfile', ROOT])
                else:
                    args.append(ROOT / 'apps' / kind)
                await self.run(*args, timeout=900)
                return {'image': image, 'built': True}
            if action == 'remove':
                info = json.loads(await self.run('image', 'inspect', image))[0]
                labels = info.get('Config', {}).get('Labels', {}) or {}
                if labels.get('phonendo.web.managed') != 'true' or labels.get('phonendo.web.kind') != kind:
                    raise ValueError('La imagen no fue construida por este panel')
                await self.run('image', 'rm', image)
                return {'image': image, 'removed': True}
            raise ValueError('Acción de imagen desconocida')

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
                key_name = body.get('verifierKey') or keys.DEFAULT_VERIFIER
                if not keys.verifier_path(key_name).is_file():
                    raise ValueError(f'No existe keys/verifiers/{key_name}.json; créala con ./tools/keys.sh verifier new {key_name}')
                config['keyPath'] = VERIFIER_KEY
            if kind == 'publisher':
                config['circuitsPath'] = '/circuits'
                wallet = body.get('wallet') or config.get('stellar', {}).get('source') or keys.DEFAULT_WALLET
                if not keys.wallet_path(wallet).is_file():
                    raise ValueError(f'No existe la cartera {wallet} en keys/stellar; créala con ./tools/keys.sh wallet new {wallet}')
                config.setdefault('stellar', {}).update(source=wallet, configDir=STELLAR_DIR)
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
                    await self.run('build', '--label', 'phonendo.web.managed=true', '--label', 'phonendo.web.kind=' + kind, '-t', image, '-f', ROOT / 'apps/publisher/Dockerfile', ROOT, timeout=900)
                else:
                    await self.run('build', '--label', 'phonendo.web.managed=true', '--label', 'phonendo.web.kind=' + kind, '-t', image, ROOT / 'apps' / kind, timeout=900)
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
                      'environment': environment, 'control': control}
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
            if kind == 'verifier':
                args.extend(['--mount', f'type=bind,src={keys.verifier_path(key_name)},dst={VERIFIER_KEY},readonly'])
            if kind == 'publisher':
                (ROOT / 'circuits/build').mkdir(exist_ok=True)
                args.extend(['--mount', f'type=bind,src={ROOT / "circuits/scripts"},dst=/circuits/scripts,readonly',
                             '--mount', f'type=bind,src={ROOT / "circuits/build"},dst=/circuits/build',
                             '--mount', f'type=bind,src={keys.WALLETS},dst={STELLAR_DIR}/identity,readonly'])
            args.append(image)
            if kind == 'reader':
                args.extend(['python', '/opt/phonendo/tools/web_runtime.py'])
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
        if identifier.startswith('compose-'):
            return await self.compose_snapshot(identifier)
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
        if identifier.startswith('compose-'):
            snapshot = await self.compose_snapshot(identifier)
            return (await self.run('logs', '--tail', '150', snapshot['container'])).splitlines()
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
            if identifier.startswith('compose-'):
                snapshot = await self.compose_snapshot(identifier)
                action = body['action']
                if action in ('start', 'stop', 'restart'):
                    args = ['stop', '--time', '5'] if action == 'stop' else [action]
                    await self.run(*args, snapshot['container'], timeout=60)
                    return await self.compose_snapshot(identifier)
                if action == 'remove':
                    await self.run('rm', '-f', snapshot['container'])
                    return {'removed': True, 'dataRetained': True}
                if action == 'config':
                    kind = snapshot['kind']
                    path = (ROOT / 'deploy/docker' / f'{kind}.json').resolve()
                    info = json.loads(await self.run('inspect', snapshot['container']))[0]
                    mounted = any(Path(item.get('Source', '')).resolve() == path and
                                  item.get('Destination') == f'/app/{kind}/config.json'
                                  for item in info.get('Mounts', []))
                    if not mounted or not path.is_file() or not path.is_relative_to((ROOT / 'deploy/docker').resolve()):
                        raise ValueError('No se puede editar la configuración de este contenedor Compose')
                    previous = json.loads(path.read_text())
                    config = restore(body['config'], previous)
                    if not isinstance(config, dict):
                        raise ValueError('La configuración debe ser un objeto JSON')
                    config.setdefault('server', {}).update(host='0.0.0.0', port=PORTS[kind])
                    if kind == 'verifier':
                        config['keyPath'] = VERIFIER_KEY
                    if kind == 'publisher':
                        config['circuitsPath'] = '/circuits'
                    # El volumen bind necesita conservar el mismo inodo.
                    path.write_text(json.dumps(config, indent=2) + '\n')
                    try:
                        await self.run('restart', snapshot['container'], timeout=60)
                    except Exception:
                        path.write_text(json.dumps(previous, indent=2) + '\n')
                        raise
                    return await self.compose_snapshot(identifier)
                raise ValueError('Acción Docker desconocida')
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
                    config['keyPath'] = VERIFIER_KEY
                if record['kind'] == 'publisher':
                    config['circuitsPath'] = '/circuits'
                    config.setdefault('stellar', {})['configDir'] = STELLAR_DIR
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
