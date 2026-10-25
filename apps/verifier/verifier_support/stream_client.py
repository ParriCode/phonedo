"""Reconnectable SSE subscription with an independent worker per source."""
import json
import threading
import requests
from .logger import Logger


class StreamClient:
    def __init__(self, urls, token, on_event, retry_seconds=5, service_url=None):
        self.urls = urls
        self.token = token
        self.on_event = on_event
        self.retry_seconds = retry_seconds
        self.stopped = threading.Event()
        self.threads = []
        self.service_url = service_url

    def start(self):
        if self.threads:
            return
        for url in self.urls:
            thread = threading.Thread(target=self._run, args=(url,), daemon=True)
            self.threads.append(thread)
            thread.start()

    def _run(self, target):
        target = {'url': target} if isinstance(target, str) else target
        url = target['url']
        token = target.get('token', self.token)
        while not self.stopped.is_set():
            try:
                headers = {'Authorization': 'Bearer ' + token} if token else {}
                if self.service_url:
                    headers['X-Phonendo-Service-URL'] = self.service_url
                with requests.get(url, headers=headers, stream=True, timeout=(10, 30)) as response:
                    response.raise_for_status()
                    kind, data = '', []
                    for line in response.iter_lines(chunk_size=1):
                        if self.stopped.is_set():
                            return
                        line = line.decode('utf-8')
                        if not line:
                            if kind == 'stream_closed':
                                break
                            if kind == 'observation' and data:
                                self.on_event(json.loads('\n'.join(data)))
                            kind, data = '', []
                        elif line.startswith('event:'):
                            kind = line[6:].strip()
                        elif line.startswith('data:'):
                            data.append(line[5:].lstrip())
            except (requests.RequestException, ValueError, TypeError) as error:
                Logger.warning('stream_connection_failed', url=url, error=str(error))
            self.stopped.wait(self.retry_seconds)

    def close(self):
        self.stopped.set()
        for thread in self.threads:
            thread.join(timeout=1)
