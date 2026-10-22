"""Optional HTTP metadata API and live SSE transport."""
import asyncio
import hmac
import json

from aiohttp import web


class AiohttpReaderServer:
    def __init__(self, service, stream, *, host="127.0.0.1", port=3002, token="",
                 stream_enabled=True):
        self.service = service
        self.stream = stream
        self.host = host
        self.port = int(port)
        self.token = token
        self.stream_enabled = stream_enabled
        self.runner = None
        self.app = web.Application(middlewares=[self.authorize])
        self.app.add_routes([
            web.get("/health", self.health),
            web.get("/metadata", self.metadata),
            web.get("/devices", self.devices),
        ])
        if stream_enabled:
            self.app.router.add_get("/observations/stream", self.observations)

    @web.middleware
    async def authorize(self, request, handler):
        if self.token and not hmac.compare_digest(
            request.headers.get("Authorization", "").encode(),
            ("Bearer " + self.token).encode(),
        ):
            raise web.HTTPUnauthorized()
        return await handler(request)

    async def health(self, request):
        return web.json_response({"status": "ok"})

    async def metadata(self, request):
        return web.json_response(self.service.metadata(stream_enabled=self.stream_enabled))

    async def devices(self, request):
        return web.json_response(self.service.devices())

    async def observations(self, request):
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

    async def start(self):
        self.runner = web.AppRunner(self.app, shutdown_timeout=2)
        await self.runner.setup()
        try:
            await web.TCPSite(self.runner, self.host, self.port).start()
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        self.stream.close()
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
