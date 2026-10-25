"""Manager HTTP routes and SSE endpoints."""
import os
import time
import threading
import hmac
from flask import g, request, abort
from manager_support.logger import Logger
from manager_support.event_stream import EventStream
from manager_support.server_stream import stream_response
from manager_support.transport import endpoint, http_endpoints


class ManagerServer:
    def __init__(self, app, config):
        self.config = config
        self._connections = set()
        self._connections_lock = threading.Lock()
        self.own_stream = EventStream()
        if config.stream_enabled:
            app.add_url_rule('/stream', 'stream',
                             lambda: self._response(self.own_stream, config.api_token_manager))
        self.verifier_stream = EventStream()
        self.storage_stream = EventStream()
        if config.output_verifiers:
            app.add_url_rule('/stream/verifier', 'stream_verifier',
                             lambda: self._service_response('verifier', self.verifier_stream, config.api_token_verifier))
        if config.output_storages:
            app.add_url_rule('/stream/storage', 'stream_storage',
                             lambda: self._service_response('storage', self.storage_stream, config.api_token_storage))

    def _service_response(self, service, stream, token):
        if not token or not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer ' + token):
            abort(401)
        try:
            source = endpoint(request.headers.get('X-Phonendo-Service-URL', ''))
        except ValueError:
            Logger.warning('stream_identity_required', service=service)
            return {'error': 'X-Phonendo-Service-URL must identify the subscribing service'}, 400
        key = (service, source)
        uses_http = source in http_endpoints(self.config, service)
        with self._connections_lock:
            if uses_http or key in self._connections:
                Logger.warning('redundant_transport_rejected', service=service, url=source,
                               selected='http' if uses_http else 'sse',
                               rejected='sse')
                return {'error': 'A transport is already selected for this service'}, 409
            self._connections.add(key)
        Logger.info('transport_selected', service=service, url=source, transport='sse')
        released = False
        def release():
            nonlocal released
            with self._connections_lock:
                if released:
                    return
                released = True
                self._connections.discard(key)
            Logger.info('stream_connection_released', service=service, url=source)
        response = stream_response(stream, token, on_close=release)
        return response

    _response = staticmethod(stream_response)

    def publish_captured(self, event):
        if self.config.stream_enabled:
            self.own_stream.publish(event)
        if self.config.output_verifiers:
            self.verifier_stream.publish(event)

    def publish_verified(self, event):
        if self.config.stream_enabled:
            self.own_stream.publish(event)
        if self.config.output_storages:
            self.storage_stream.publish(event)


def register_routes(app, core):
    @app.get('/info')
    def info():
        connections = []
        for service in ('verifier', 'storage'):
            for url in sorted(http_endpoints(core.client.config, service)):
                connections.append({'peer': url, 'transport': 'http'})
        connections.extend({'peer': reader, 'transport': 'http'}
                           for reader in sorted(core.http_readers))
        connections.extend({'peer': reader, 'transport': 'sse'}
                           for reader in sorted(core.client.reader_streams))
        for subscription in core.client.subscriptions:
            connections.extend({'peer': url.rsplit('/stream', 1)[0], 'transport': 'sse'}
                               for url in sorted(subscription.connected))
        with core.server._connections_lock:
            connections.extend({'peer': url, 'transport': 'sse'}
                               for _, url in sorted(core.server._connections))
        connections.extend({'peer': peer, 'transport': 'sse'}
                           for peer in core.server.own_stream.peers())
        return connections

    @app.get('/logs')
    def logs():
        return list(Logger.instance().messages)

    @app.before_request
    def start_request_log():
        g.request_started_at = time.time()

    @app.after_request
    def log_request(response):
        if request.path in ('/info', '/logs'):
            return response
        duration_ms = int((time.time() - g.get("request_started_at", time.time())) * 1000)
        body = request.get_json(silent=True) or {}

        Logger.request(
            request.method,
            request.path,
            response.status_code,
            durationMs=duration_ms,
            deviceId=body.get("deviceId") if isinstance(body, dict) else None,
            readerId=body.get("readerId") if isinstance(body, dict) else None,
        )
        return response

    @app.get("/")
    def alive():
        return "Service is alive"

    @app.post("/newEvent")
    def new_event():
        body = request.get_json(silent=True) or {}

        if not body.get("token") or body.get("token") != os.getenv("API_TOKEN_MANAGER"):
            Logger.warning("manager_new_event_not_authorized")
            return "Not authorized", 401


        device_id           = body.get("deviceId")
        reader_id           = body.get("readerId")
        payload             = body.get("payload")
        payload_format      = body.get("payloadFormat")
        event_type          = body.get("eventType")


        if not device_id:
            Logger.warning("manager_new_event_bad_request", missing="deviceId")
            return {"error": "deviceId is required"}, 400

        if not reader_id:
            Logger.warning("manager_new_event_bad_request", missing="readerId")
            return {"error": "readerId is required"}, 400

        if not payload:
            Logger.warning("manager_new_event_bad_request", missing="payload")
            return {"error": "payload is required"}, 400

        if not payload_format:
            Logger.warning("manager_new_event_bad_request", missing="payloadFormat")
            return {"error": "payloadFormat is required"}, 400

        if not event_type:
            Logger.warning("manager_new_event_bad_request", missing="eventType")
            return {"error": "eventType is required"}, 400

        if not core.prefer_http(reader_id):
            return {'error': 'This Reader already uses SSE with this Manager'}, 409

        return core.submit_observation(body)
