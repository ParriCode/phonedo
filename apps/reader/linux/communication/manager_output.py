"""Sequential manager delivery without blocking source acquisition or SSE."""
import asyncio

from logger import Logger


class ManagerOutput:
    def __init__(self, client, *, register=True, send=True, queue_size=256):
        if not isinstance(queue_size, int) or queue_size < 1:
            raise ValueError("manager queue_size must be a positive integer")
        self.client = client
        self.register = register
        self.send = send
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.devices = {}
        self.registered = set()

    def register_device(self, reader_id, device):
        self.devices[device.device_id] = (reader_id, device)
        if self.register:
            self._enqueue(("register", device.device_id))

    def publish(self, ttl, reader_id, device_id):
        if self.send:
            self._enqueue(("observation", (ttl, reader_id, device_id)))

    def _enqueue(self, item):
        try:
            self.queue.put_nowait(item)
        except asyncio.QueueFull:
            Logger.error("manager_queue_full", droppedKind=item[0])

    def _ensure_registered(self, device_id):
        if self.register and device_id not in self.registered:
            reader_id, device = self.devices[device_id]
            self.client.register_device(reader_id, device)
            self.registered.add(device_id)

    def _deliver(self, item):
        kind, value = item
        if kind == "register":
            self._ensure_registered(value)
        else:
            ttl, reader_id, device_id = value
            self._ensure_registered(device_id)
            self.client.send_observation_ttl(ttl, reader_id, device_id)

    async def deliver_next(self):
        item = await self.queue.get()
        try:
            await asyncio.to_thread(self._deliver, item)
        except Exception as error:
            Logger.error("manager_delivery_failed", error=str(error), kind=item[0])
        finally:
            self.queue.task_done()

    async def run(self):
        while True:
            await self.deliver_next()
