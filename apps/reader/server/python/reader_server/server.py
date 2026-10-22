"""Server composition; domain objects enter through ReaderCore callbacks."""
from dataclasses import dataclass
from .service import ReaderService
from .stream import ObservationStream, StreamOutput


@dataclass(frozen=True)
class ServerConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 3002
    token: str = ""
    stream_enabled: bool = True
    queue_size: int = 256


class ReaderServer:
    """Single-use lifecycle: create -> start -> stop -> dispose."""
    def __init__(self, core, config=None, *, outputs=()):
        self.core = core
        self.config = config if config is not None else ServerConfig()
        self.stream = (ObservationStream(self.config.queue_size)
                       if self.config.stream_enabled else None)
        service_outputs = list(outputs)
        if self.stream is not None:
            service_outputs.insert(0, StreamOutput(self.stream))
        self.service = ReaderService(core, tuple(service_outputs))
        self.transport = None
        self.running = False
        self._stopped = False
        if self.config.enabled:
            from .http import AiohttpReaderServer
            self.transport = AiohttpReaderServer(
                self.service, self.stream, host=self.config.host,
                port=self.config.port, token=self.config.token,
                stream_enabled=self.config.stream_enabled,
            )

    @property
    def app(self):
        if self.transport is None:
            raise RuntimeError("HTTP server is disabled")
        return self.transport.app

    async def start(self):
        if self.running or self.transport is None:
            return
        if self._stopped:
            raise RuntimeError("ReaderServer is disposed; create a new instance")
        await self.transport.start()
        self.running = True

    async def stop(self):
        if self._stopped:
            return
        try:
            if self.stream is not None:
                self.stream.close()
            if self.transport is not None:
                await self.transport.stop()
        finally:
            self.running = False
            self._stopped = True

    def status(self):
        return {"running": self.running, "http_enabled": self.config.enabled,
                "readerId": self.core.reader_id}
