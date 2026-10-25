"""Outbound HTTP operations used by the Manager."""

import requests

from manager_support.logger import Logger
from manager_support.transport import endpoint, http_endpoints


class InternalPostError(RuntimeError):
    def __init__(self, url: str, status: int, body: str):
        super().__init__(f"{url} returned {status}: {body}")
        self.url = url
        self.status = status
        self.body = body


class ManagerClient:
    def __init__(self, config, timeout: float = 10):
        self.config = config
        self.timeout = timeout
        self.reader_streams = set()
        self.subscriptions = []


    def _targets(self, service):
        targets = getattr(self.config, service + '_url_list')
        if not targets:
            raise RuntimeError(f'No {service} configured in services.{service}s')
        seen = set()
        for target in targets:
            target = {'url': target} if isinstance(target, str) else target
            base = endpoint(target)
            if base in seen:
                Logger.warning('duplicate_destination_ignored', service=service, url=base)
                continue
            seen.add(base)
            yield base, target.get(
                'token', getattr(self.config, 'api_token_' + service))

    def _broadcast(self, service, path, message, completed=None):
        responses, errors = [], []
        for base, token in self._targets(service):
            if completed is not None and base in completed:
                responses.append(message)
                continue
            try:
                reply = self._post(base + path, {'token': token, 'message': message})
                if completed is not None:
                    confirmed = reply.get('message', reply) if isinstance(reply, dict) else reply
                    if confirmed != message:
                        raise RuntimeError('Storage did not confirm the verified message')
                    completed.add(base)
                responses.append(reply)
            except (requests.RequestException, InternalPostError) as error:
                errors.append(error)
        if errors:
            raise errors[0]
        return responses

    def verify_event(self, message: dict, target=None):
        if target is None:
            targets = list(self._targets('verifier'))
            if len(targets) != 1:
                raise RuntimeError('An explicit Verifier target is required')
            base, token = targets[0]
        else:
            target = {'url': target} if isinstance(target, str) else target
            base = target['url'].rstrip('/')
            token = target.get('token', self.config.api_token_verifier)
        return self._post(base + '/verify', {'token': token, 'message': message})

    def store_event(self, message: dict, completed=None):
        responses = self._broadcast('storage', '/events', message, completed)
        if any((reply.get('message', reply) if isinstance(reply, dict) else reply) != message
               for reply in responses):
            raise RuntimeError('Storage did not confirm the verified message')
        return responses[0]

    def _post(self, url: str, body: dict):
        sanitized = dict(body)
        sanitized.pop("token", None)
        Logger.debug("internal_post_request", url=url, body=sanitized)
        response = requests.post(url, json=body, timeout=self.timeout)
        Logger.debug("internal_post_response", url=url, status=response.status_code,
                     body=response.text)
        if not response.ok:
            raise InternalPostError(url, response.status_code, response.text)
        try:
            return response.json()
        except ValueError:
            return response.text

    def consume_reader_stream(self, reader_url: str, on_event, stop_event, core=None):
        """Consume one Reader SSE connection; caller handles reconnection."""
        target = {'url': reader_url} if isinstance(reader_url, str) else reader_url
        base_url = target['url'].rstrip('/')
        headers = {}
        token = target.get('token', self.config.api_token_reader)
        if token:
            headers['Authorization'] = f'Bearer {token}'
        metadata = requests.get(f'{base_url}/metadata', headers=headers,
                                timeout=self.timeout)
        metadata.raise_for_status()
        details = metadata.json()
        if not isinstance(details, dict):
            raise ValueError(f'Reader at {base_url} returned invalid metadata')
        reader_id = details.get('readerId')
        capabilities = details.get('capabilities')
        if (not isinstance(reader_id, str) or not reader_id
                or not isinstance(capabilities, dict)
                or capabilities.get('stream') is not True):
            raise ValueError(f'Reader at {base_url} has no usable stream metadata')

        if core is not None and not core.acquire_reader_stream(reader_id):
            # A selected HTTP transport must not trigger repeated SSE attempts.
            return False
        try:
            self._read_reader_stream(base_url, headers, reader_id, on_event, stop_event, core)
        finally:
            self.reader_streams.discard(reader_id)
            if core is not None:
                core.release_reader_stream(reader_id)
        return True

    def _read_reader_stream(self, base_url, headers, reader_id, on_event, stop_event, core=None):
        import json
        with requests.get(f'{base_url}/stream', headers=headers, stream=True,
                          timeout=(self.timeout, 30)) as response:
            response.raise_for_status()
            self.reader_streams.add(reader_id)
            if core is not None:
                core.activate_reader_stream(reader_id)
            event_type = None
            data = []
            for line in response.iter_lines(decode_unicode=True):
                if stop_event.is_set():
                    break
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                if line == '':
                    if event_type == 'observation' and data:
                        try:
                            event = json.loads('\n'.join(data))
                        except ValueError:
                            Logger.warning('reader_stream_invalid_json', readerId=reader_id)
                        else:
                            if isinstance(event, dict) and event.get('readerId') == reader_id:
                                on_event(event)
                            else:
                                Logger.warning('reader_stream_identity_mismatch', readerId=reader_id)
                    elif event_type == 'stream_closed':
                        break
                    event_type, data = None, []
                elif line.startswith('event:'):
                    event_type = line[6:].strip()
                elif line.startswith('data:'):
                    data.append(line[5:].lstrip())

    def start_reader_subscriptions(self, on_event, core=None):
        """Start configured Reader subscriptions and return a stop function."""
        import threading

        stop_event = threading.Event()
        threads = []
        seen = set()
        if self.config.reader_subscriptions:
            for reader_url in self.config.reader_subscriptions:
                source = endpoint(reader_url)
                if source in seen:
                    Logger.warning('duplicate_subscription_ignored', service='reader', url=source)
                    continue
                seen.add(source)
                def run(url=reader_url):
                    while not stop_event.is_set():
                        try:
                            if self.consume_reader_stream(url, on_event, stop_event, core) is False:
                                return
                        except (requests.RequestException, ValueError) as error:
                            Logger.warning('reader_stream_disconnected', url=url, error=str(error))
                        stop_event.wait(5)
                thread = threading.Thread(target=run, name=f'reader-stream-{reader_url}',
                                          daemon=True)
                thread.start()
                threads.append(thread)

        def stop():
            stop_event.set()
            for thread in threads:
                thread.join(timeout=1)
        return stop

    def start_subscriptions(self, core):
        from manager_support.stream_client import StreamClient
        stops = [self.start_reader_subscriptions(core.on_reader_stream_event, core)]
        for service, targets, callback in (
                ('verifier', self.config.verifier_subscriptions, core.on_verifier_stream_event),
                ('storage', self.config.storage_subscriptions, core.on_storage_stream_event)):
            seen = set()
            for entry in targets:
                target = {'url': entry} if isinstance(entry, str) else dict(entry)
                source = endpoint(target)
                if source in http_endpoints(self.config, service) or source in seen:
                    Logger.warning('redundant_subscription_ignored', service=service, url=source,
                                   selected='http' if source in http_endpoints(self.config, service) else 'sse')
                    continue
                seen.add(source)
                target['url'] = source + '/stream'
                client = StreamClient([target], getattr(self.config, 'api_token_' + service),
                    lambda message, source=source, callback=callback: callback(source, message))
                client.start()
                self.subscriptions.append(client)
                stops.append(client.close)
        def stop():
            for close in stops:
                close()
        return stop
