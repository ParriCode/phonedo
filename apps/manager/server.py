"""Flask SSE endpoints for downstream services.

The current HTTP POST workflow remains active. Consumers can subscribe when ready.
"""
from contextlib import contextmanager
import hmac
import json
import queue
import threading

from flask import Response, abort, request


class EventStream:
    def __init__(self, queue_size=256):
        self.queue_size = queue_size
        self._subscribers = set()
        self._lock = threading.Lock()

    @contextmanager
    def subscribe(self):
        subscriber = queue.Queue(maxsize=self.queue_size)
        with self._lock:
            self._subscribers.add(subscriber)
        try:
            yield subscriber
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)

    def publish(self, event):
        with self._lock:
            for subscriber in tuple(self._subscribers):
                try:
                    subscriber.put_nowait(event)
                except queue.Full:
                    self._subscribers.discard(subscriber)
                    while not subscriber.empty():
                        subscriber.get_nowait()
                    subscriber.put_nowait(None)


class ManagerServer:
    def __init__(self, app, config):
        self.config = config
        self.verifier_stream = EventStream()
        self.storage_stream = EventStream()
        if config.stream and config.stream_verifiers:
            app.add_url_rule('/stream/verifier', 'stream_verifier',
                             lambda: self._response(self.verifier_stream, config.api_token_verifier))
        if config.stream and config.stream_storages:
            app.add_url_rule('/stream/storage', 'stream_storage',
                             lambda: self._response(self.storage_stream, config.api_token_storage))

    @staticmethod
    def _response(stream, token):
        supplied = request.headers.get('Authorization', '')
        if not token or not hmac.compare_digest(supplied, 'Bearer ' + token):
            abort(401)

        def events():
            with stream.subscribe() as subscriber:
                yield ': connected\n\n'
                while True:
                    try:
                        event = subscriber.get(timeout=15)
                    except queue.Empty:
                        yield ': heartbeat\n\n'
                        continue
                    if event is None:
                        yield 'event: stream_closed\ndata: {}\n\n'
                        break
                    yield ('event: observation\nid: ' + str(event['key']) + '\ndata: '
                           + json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n\n')

        return Response(events(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    def publish_captured(self, event):
        if self.config.stream and self.config.stream_verifiers:
            self.verifier_stream.publish(event)

    def publish_verified(self, event):
        if self.config.stream and self.config.stream_storages:
            self.storage_stream.publish(event)
