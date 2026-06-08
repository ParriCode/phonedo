import asyncio
import contextlib
import inspect
from abc import ABC, abstractmethod


class BaseDeviceManager(ABC):
    def __init__(self, on_measurement):
        self.on_measurement = on_measurement
        self._running = False
        self._tasks = set()

    async def start(self):
        self._running = True
        try:
            await self._run()
        finally:
            self._running = False
            await self.stop()

    async def stop(self):
        self._running = False

        for task in self._tasks:
            task.cancel()

        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._tasks.clear()

    async def _emit(self, observation):
        result = self.on_measurement(observation)
        if inspect.isawaitable(result):
            await result

    def _task(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    @abstractmethod
    async def _run(self):
        pass