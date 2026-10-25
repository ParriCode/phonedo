"""Manager HTTP routes and SSE endpoints."""
import os
import time
from flask import g, request
from manager_support.logger import Logger
from manager_support.event_stream import EventStream
from manager_support.server_stream import stream_response


class ManagerServer:
    def __init__(self, app, config):
        self.config = config
        self.own_stream = EventStream()
        if config.stream_enabled:
            app.add_url_rule('/stream', 'stream',
                             lambda: self._response(self.own_stream, config.api_token_manager))
        self.verifier_stream = EventStream()
        self.storage_stream = EventStream()
        if config.output_verifiers:
            app.add_url_rule('/stream/verifier', 'stream_verifier',
                             lambda: self._response(self.verifier_stream, config.api_token_verifier))
        if config.output_storages:
            app.add_url_rule('/stream/storage', 'stream_storage',
                             lambda: self._response(self.storage_stream, config.api_token_storage))

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

    @app.before_request
    def start_request_log():
        g.request_started_at = time.time()

    @app.after_request
    def log_request(response):
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

        # Once a Reader uses HTTP, its SSE observations are ignored for this process.
        core.prefer_http(reader_id)

        return core.submit_observation(body)
