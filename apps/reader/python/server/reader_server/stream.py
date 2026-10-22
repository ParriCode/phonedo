"""Live fan-out. Each subscriber owns a bounded queue."""
import asyncio
from contextlib import contextmanager


class ObservationStream:
    def __init__(self, queue_size=256):
        if not isinstance(queue_size, int) or queue_size < 1:
            raise ValueError("stream queue_size must be a positive integer")
        self.queue_size = queue_size
        self._subscribers = set()

    @contextmanager
    def subscribe(self):
        queue = asyncio.Queue(maxsize=self.queue_size)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def publish(self, event):
        # Called on the runtime's event loop, just like the source callbacks.
        for queue in tuple(self._subscribers):
            if queue.full():
                self._disconnect(queue)
            else:
                queue.put_nowait(event)

    def _disconnect(self, queue):
        self._subscribers.discard(queue)
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(None)

    def close(self):
        for queue in tuple(self._subscribers):
            self._disconnect(queue)


class StreamOutput:
    def __init__(self, stream: ObservationStream):
        self.stream = stream

    def register_device(self, reader_id, device):
        pass

    def publish(self, reader_id, observation):
        from .serialization import observation_event
        self.stream.publish(observation_event(reader_id, observation))
