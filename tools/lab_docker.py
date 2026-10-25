"""Docker lifecycle for the desktop lab; resources belong to one lab session."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import urllib.request
import urllib.error
import uuid

ROOT = Path(__file__).resolve().parents[1]
PORTS = {'reader': 3002, 'manager': 3003, 'verifier': 5000, 'storage': 5000}


class DockerSession:
    def __init__(self, events):
        self.events = events
        self.network = 'phonendo-lab-' + uuid.uuid4().hex[:10]
        self.instances = []
        self.connected = False
        self.credentials = {'API_TOKEN_MANAGER': 'lab-manager', 'API_TOKEN_STORAGE': 'lab-storage',
                            'API_TOKEN_VERIFIER': 'lab-verifier', 'MANAGER_PASSWORD': uuid.uuid4().hex}

    def run(self, *args, timeout=120):
        result = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Error de Docker')
        return result.stdout.strip()

    def connect(self):
        if not self.connected:
            self.run('info', '--format', '{{.ServerVersion}}', timeout=10)
            self.run('network', 'create', self.network)
            self.connected = True

    def build(self, kind):
        self.events.put(('Docker', f'Construyendo imagen de {kind}…\n'))
        tag = 'phonendo-lab-' + kind
        self.run('build', '-t', tag, ROOT / 'apps' / kind, timeout=600)
        self.events.put(('Docker', f'Imagen {tag} preparada.\n'))
        return tag

    def remove_all(self):
        removed, errors = [], []
        for instance in list(self.instances):
            try:
                removed.append(instance.remove())
            except Exception as error:
                errors.append(f'{instance.name}: {error}')
        return {'removed': removed, 'errors': errors}

    def close(self):
        result = self.remove_all()
        if result['errors']:
            raise RuntimeError('\n'.join(result['errors']))
        if self.connected:
            self.run('network', 'rm', self.network)
            self.connected = False


class DockerInstance:
    def __init__(self, session, kind, name, port, config):
        if kind not in PORTS or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', name):
            raise ValueError('Nombre: usa letras, números, guiones y puntos')
        if not 1 <= port <= 65535:
            raise ValueError('El puerto local debe estar entre 1 y 65535')
        if any(instance.name == name for instance in session.instances):
            raise ValueError('Ya existe una instancia con ese nombre')
        session.connect()
        image = session.build(kind)
        self.session, self.kind, self.name, self.port = session, kind, name, port
        self.internal_port = PORTS[kind]
        self.container = session.network + '-' + name
        self.directory = tempfile.TemporaryDirectory(prefix='phonendo-docker-lab-')
        folder = Path(self.directory.name)
        self.config = copy.deepcopy(config)
        self.config.setdefault('server', {}).update(host='0.0.0.0', port=self.internal_port)
        if kind == 'reader':
            self.config['server']['enabled'] = True
            self.config['labStatePath'] = '/data/reader-state.json'
        self.path = folder / 'config.json'
        self.path.write_text(json.dumps(self.config, indent=2))
        (folder / 'data').mkdir()
        args = ['run', '-d', '--user', f'{os.getuid()}:{os.getgid()}', '--name', self.container, '--network', session.network,
                '--network-alias', name, '--label', 'phonendo.lab=' + session.network,
                '-p', f'127.0.0.1:{port}:{self.internal_port}',
                '--mount', f'type=bind,src={self.path},dst=/app/{kind}/config.json,readonly',
                '--mount', f'type=bind,src={folder / "data"},dst=/data',
                '-e', f'PORT_{kind.upper()}={self.internal_port}', '-e', 'PHONENDO_VERBOSE=true']
        for key, value in session.credentials.items():
            args.extend(['-e', key + '=' + value])
        if kind == 'verifier':
            keys = ROOT / 'apps/verifier/keys.json'
            if not keys.is_file():
                self.directory.cleanup()
                raise ValueError('Falta apps/verifier/keys.json')
            args.extend(['--mount', f'type=bind,src={keys},dst=/app/verifier/keys.json,readonly'])
        if kind == 'reader':
            args.extend(['--mount', f'type=bind,src={ROOT / "tools/lab_reader.py"},dst=/lab/reader.py,readonly',
                         '-e', 'PYTHONPATH=/app/reader/python/core:/app/reader/python/server'])
        args.append(image)
        if kind == 'reader':
            args.extend(['python', '/lab/reader.py', '/app/reader/config.json', '--http'])
        try:
            session.run(*args)
        except Exception:
            session.run('rm', '-f', self.container) if self.exists() else None
            self.directory.cleanup()
            raise
        session.instances.append(self)
        self.follow_logs()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}'

    @property
    def docker_url(self):
        return f'http://{self.name}:{self.internal_port}'

    def exists(self):
        try:
            self.session.run('inspect', self.container)
            return True
        except RuntimeError:
            return False

    def state(self):
        return self.session.run('inspect', '--format', '{{.State.Status}}', self.container, timeout=10)

    def follow_logs(self):
        process = subprocess.Popen(['docker', 'logs', '-f', '--tail', '30', self.container],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        def read():
            try:
                for line in process.stdout:
                    self.session.events.put((self.name, line))
            finally:
                process.stdout.close()
                process.wait()
        threading.Thread(target=read, daemon=True).start()

    def command(self, body):
        if self.kind != 'reader' or self.state() != 'running':
            raise ValueError('Selecciona un Reader en ejecución')
        headers = {'Content-Type': 'application/json'}
        token = self.config['server'].get('token')
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(self.url + '/_lab/command',
                    data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            detail = json.loads(error.read()).get('error', str(error))
            raise ValueError(detail) from error
        self.session.events.put((self.name, json.dumps(result, ensure_ascii=False) + '\n'))
        return result

    def pause(self):
        self.session.run('pause', self.container)

    def stop(self):
        if self.state() == 'paused':
            self.session.run('unpause', self.container)
        self.session.run('stop', '--time', '3', self.container)

    def resume(self):
        state = self.state()
        if state == 'paused':
            self.session.run('unpause', self.container)
        elif state != 'running':
            self.session.run('start', self.container)
            self.follow_logs()

    def remove(self):
        if self.exists():
            self.session.run('rm', '-f', self.container)
        self.directory.cleanup()
        if self in self.session.instances:
            self.session.instances.remove(self)
        return self.name
