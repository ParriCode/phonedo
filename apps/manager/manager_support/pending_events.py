"""Bounded, volatile retry queue. One worker; callbacks run outside the lock."""
from collections import OrderedDict
import threading


class PendingEvents:
    def __init__(self, capacity, interval, process, discarded):
        if capacity < 1 or interval <= 0:
            raise ValueError('Queue capacity and retry interval must be positive')
        self.capacity, self.interval = capacity, interval
        self.process, self.discarded = process, discarded
        self._items = OrderedDict()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._sequence = 0

    def put(self, job, *, start=True):
        dropped = None
        with self._lock:
            if '_order' not in job:
                self._sequence += 1
                job['_order'] = self._sequence
            self._items[job['message']['key']] = job
            self._items = OrderedDict(sorted(self._items.items(), key=lambda item: item[1]['_order']))
            if len(self._items) > self.capacity:
                _, dropped = self._items.popitem(last=False)
            if start and (self._thread is None or not self._thread.is_alive()):
                self._thread = threading.Thread(target=self._run, daemon=True, name='manager-retries')
                self._thread.start()
        if dropped is not None:
            self.discarded(dropped)

    def retry_once(self):
        with self._lock:
            if not self._items:
                return
            _, job = self._items.popitem(last=False)
        if self.process(job):
            self.put(job, start=False)

    def _run(self):
        while not self._stop.wait(self.interval):
            self.retry_once()

    def close(self):
        self._stop.set()

    def __len__(self):
        with self._lock:
            return len(self._items)
