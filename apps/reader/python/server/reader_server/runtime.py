"""Lifecycle orchestration without platform or transport dependencies."""
import asyncio
from collections.abc import Callable, Sequence
from .contracts import Source, Server, Worker


class ReaderRuntime:
    def __init__(self, *, sources: Sequence[Source] = (), servers: Sequence[Server] = (),
                 workers: Sequence[Worker] = (), on_close: Callable[[], None] | None = None):
        self.sources = list(sources)
        self.servers = list(servers)
        self.workers = list(workers)
        self.on_close = on_close

    async def run(self) -> None:
        if not self.sources and not self.servers:
            raise RuntimeError("No hay fuentes ni servidor activos.")
        tasks = []
        started_servers = []
        try:
            for server in self.servers:
                started_servers.append(server)
                await server.start()
            tasks.extend(asyncio.create_task(worker.run()) for worker in self.workers)
            tasks.extend(asyncio.create_task(source.start()) for source in self.sources)
            if tasks:
                await asyncio.gather(*tasks)
            else:
                await asyncio.Event().wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.gather(*(source.stop() for source in self.sources), return_exceptions=True)
            try:
                if self.on_close:
                    self.on_close()
            finally:
                await asyncio.gather(*(server.stop() for server in reversed(started_servers)),
                                     return_exceptions=True)
