"""HTTP observation output targeting any number of independent Managers."""
import json
from collections import deque
import logging
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .serialization import observation_event


class ManagerOutput:
    def __init__(self, managers, *, timeout=10):
        self.managers = tuple(managers)
        self.timeout = timeout
        self.messages = deque(maxlen=200)

    @classmethod
    def from_config(cls, path):
        config = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(config.get('services', {}).get('managers', []),
                   timeout=config.get('httpTimeoutSeconds', 10))

    def _send(self, path, body):
        results = []
        for target in self.managers:
            target = {'url': target} if isinstance(target, str) else target
            url = target['url'].rstrip('/') + path
            data = json.dumps({**body, 'token': target.get('token', '')}).encode('utf-8')
            request = Request(url, data=data, headers={'Content-Type': 'application/json'})
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    self.messages.append('manager_http_delivery_ok')
                    results.append({'url': url, 'status': response.status})
            except (URLError, TimeoutError) as error:
                self.messages.append('manager_http_delivery_failed')
                logging.getLogger(__name__).warning('Manager delivery failed: %s: %s', url, error)
                results.append({'url': url, 'error': str(error)})
        return results

    def publish(self, reader_id, observation):
        return self._send('/newEvent', observation_event(reader_id, observation))
