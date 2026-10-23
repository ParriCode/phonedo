"""Outbound HTTP operations used by the Manager."""

import requests

from manager_support.logger import Logger


class DeviceNotRegisteredError(RuntimeError):
    pass


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


    #Obtener dispositivo de la base de datos del storage, si no existe lanza un error DeviceNotRegisteredError
    def get_device(self, device_id: str) -> dict:
        url = f"{self.config.storage_devices_url.rstrip('/')}/{device_id}"
        Logger.debug("storage_device_lookup_request", url=url, deviceId=device_id)
        response = requests.get(
            url,
            headers={"X-Storage-Token": self.config.api_token_storage},
            timeout=self.timeout,
        )
        if response.status_code == 404:
            Logger.warning("storage_device_not_registered", deviceId=device_id)
            raise DeviceNotRegisteredError("Device not registered")
        if response.status_code != 200:
            Logger.error("storage_device_lookup_failed", deviceId=device_id,
                         status=response.status_code, body=response.text)
            raise RuntimeError(f"Storage error: {response.status_code} {response.text}")
        Logger.info("storage_device_found", deviceId=device_id)
        return response.json()["value"]
    #Registrar un dispositivo en la base de datos del storage
    def register_device(self, message: dict):
        return self._post(self.config.storage_register_devices_url, {
            "token": self.config.api_token_storage, "message": message,
        })

    def verify_event(self, message: dict):
        return self._post(self.config.verifier_verify_url, {
            "token": self.config.api_token_verifier, "message": message,
        })

    def store_event(self, message: dict):
        return self._post(self.config.storage_events_url, {
            "token": self.config.api_token_storage, "message": message,
        })

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

    def consume_reader_stream(self, reader_url: str, on_event, stop_event) -> None:
        """Consume one Reader SSE connection; caller handles reconnection."""
        import json

        base_url = reader_url.rstrip('/')
        headers = {}
        if self.config.api_token_reader:
            headers['Authorization'] = f'Bearer {self.config.api_token_reader}'
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

        with requests.get(f'{base_url}/stream', headers=headers, stream=True,
                          timeout=(self.timeout, 30)) as response:
            response.raise_for_status()
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

    def start_reader_streams(self, on_event):
        """Start configured Reader subscriptions and return a stop function."""
        import threading

        stop_event = threading.Event()
        threads = []
        if self.config.stream and self.config.stream_readers:
            for reader_url in self.config.reader_url_list:
                def run(url=reader_url):
                    while not stop_event.is_set():
                        try:
                            self.consume_reader_stream(url, on_event, stop_event)
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
