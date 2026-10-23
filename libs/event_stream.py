from contextlib import contextmanager
import queue
import threading

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


