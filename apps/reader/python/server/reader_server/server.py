"""Server composition; domain objects enter through ReaderCore callbacks."""
import asyncio
import hmac
import json
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
        self._app = None
        self.runner = None
        self.running = False
        self._stopped = False
        if self.config.enabled:
            from aiohttp import web

            @web.middleware
            async def authorize(request, handler):
                if self.config.token and not hmac.compare_digest(
                    request.headers.get("Authorization", "").encode(),
                    ("Bearer " + self.config.token).encode(),
                ):
                    raise web.HTTPUnauthorized()
                return await handler(request)

            self._app = web.Application(middlewares=[authorize])
            self._app.add_routes([
                web.get("/health", self.health),
                web.get("/metadata", self.metadata),
                web.get("/devices", self.devices),
            ])
            if self.stream is not None:
                self._app.router.add_get("/observations/stream", self.observations)

    @property
    def app(self):
        if self._app is None:
            raise RuntimeError("HTTP server is disabled")
        return self._app

    async def start(self):
        if self.running or not self.config.enabled:
            return
        if self._stopped:
            raise RuntimeError("ReaderServer is disposed; create a new instance")
        from aiohttp import web
        self.runner = web.AppRunner(self.app, shutdown_timeout=2)
        try:
            await self.runner.setup()
            await web.TCPSite(self.runner, self.config.host, int(self.config.port)).start()
            self.running = True
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        if self._stopped:
            return
        try:
            if self.stream is not None:
                self.stream.close()
            if self.runner is not None:
                await self.runner.cleanup()
        finally:
            self.runner = None
            self.running = False
            self._stopped = True

    def status(self):
        return {"running": self.running, "http_enabled": self.config.enabled,
                "readerId": self.core.reader_id}

    async def health(self, request):
        from aiohttp import web
        return web.json_response({"status": "ok"})

    async def metadata(self, request):
        from aiohttp import web
        return web.json_response(self.service.metadata(stream_enabled=self.config.stream_enabled))

    async def devices(self, request):
        from aiohttp import web
        return web.json_response(self.service.devices())

    async def observations(self, request):
        from aiohttp import web
        response = web.StreamResponse(headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })
        with self.stream.subscribe() as queue:
            await response.prepare(request)
            try:
                await response.write(b": connected\n\n")
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                    except asyncio.TimeoutError:
                        chunk = b": heartbeat\n\n"
                    else:
                        if event is None:
                            await response.write(
                                b'event: stream_closed\ndata: {}\n\n'
                            )
                            break
                        chunk = ("event: observation\ndata: "
                                 + json.dumps(event) + "\n\n").encode()
                    await asyncio.wait_for(response.write(chunk), timeout=15)
            except (ConnectionError, asyncio.TimeoutError):
                pass
        return response
