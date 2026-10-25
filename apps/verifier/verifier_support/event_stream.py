from contextlib import contextmanager
import queue
import threading

class EventStream:
    def __init__(self, queue_size=256):
        self.queue_size = queue_size
        self._subscribers = set()
        self._peers = {}
        self._lock = threading.Lock()

    @contextmanager
    def subscribe(self, peer=None):
        subscriber = queue.Queue(maxsize=self.queue_size)
        with self._lock:
            self._subscribers.add(subscriber)
            self._peers[subscriber] = peer
        try:
            yield subscriber
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)
                self._peers.pop(subscriber, None)

    def peers(self):
        with self._lock:
            return [peer for peer in self._peers.values() if peer is not None]

    def publish(self, event):
        with self._lock:
            for subscriber in tuple(self._subscribers):
                try:
                    subscriber.put_nowait(event)
                except queue.Full:
                    self._subscribers.discard(subscriber)
                    self._peers.pop(subscriber, None)
                    while not subscriber.empty():
                        subscriber.get_nowait()
                    subscriber.put_nowait(None)


