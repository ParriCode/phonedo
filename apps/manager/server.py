"""Manager HTTP routes and SSE endpoints."""
import os
import time
from flask import g, request
from manager_support.logger import Logger
from client import InternalPostError
from manager_support.event_stream import EventStream
from manager_support.server_stream import stream_response


class ManagerServer:
    def __init__(self, app, config):
        self.config = config
        self.verifier_stream = EventStream()
        self.storage_stream = EventStream()
        if config.stream and config.stream_verifiers:
            app.add_url_rule('/stream/verifier', 'stream_verifier',
                             lambda: self._response(self.verifier_stream, config.api_token_verifier))
        if config.stream and config.stream_storages:
            app.add_url_rule('/stream/storage', 'stream_storage',
                             lambda: self._response(self.storage_stream, config.api_token_storage))

    _response = staticmethod(stream_response)

    def publish_captured(self, event):
        if self.config.stream and self.config.stream_verifiers:
            self.verifier_stream.publish(event)

    def publish_verified(self, event):
        if self.config.stream and self.config.stream_storages:
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

    @app.post("/registerDevice")
    def register_device():
        #Obtener cuerpo del mensaje
        body = request.get_json(silent=True) or {}
        #Es necesario el TOKEN para el manager
        if not body.get("token") or body.get("token") != os.getenv("API_TOKEN_MANAGER"):
            Logger.warning("manager_register_device_not_authorized")
            return "Not authorized", 401


        #Obtener campos del cuerpo json
        schema_version      = body.get("schemaVersion")
        device_id           = body.get("deviceId")
        reader_id           = body.get("readerId")
        device_type         = body.get("deviceType")
        creation_date_time  = body.get("creationDatetime")

        #verificar que todos los cuerpos existen
        if not schema_version:
            Logger.warning("manager_register_device_bad_request", missing="schemaVersion")
            return {"error": "schemaVersion is required"}, 400

        if not device_id:
            Logger.warning("manager_register_device_bad_request", missing="deviceId")
            return {"error": "deviceId is required"}, 400

        if not reader_id:
            Logger.warning("manager_register_device_bad_request", missing="readerId")
            return {"error": "readerId is required"}, 400

        if not device_type:
            Logger.warning("manager_register_device_bad_request", missing="deviceType")
            return {"error": "deviceType is required"}, 400

        if not creation_date_time:
            Logger.warning("manager_register_device_bad_request", missing="creationDatetime")
            return {"error": "creation_date_time is requires"}, 400


        Logger.info("device_register_received", deviceId=device_id, readerId=reader_id)

        message = {
            "key": device_id,
            "value": {
                "deviceId": device_id,
                "deviceType": device_type,
                "registeredByReader": reader_id,
                "registrationDatetime": int(time.time() * 1000),
            },
        }

        try:
            response = core.client.register_device(message)

            Logger.info("device_registered", deviceId=device_id, readerId=reader_id)
            Logger.debug("device_register_storage_response", response=response)
        except InternalPostError as error:
            Logger.error(
                "device_register_failed",
                deviceId=device_id,
                readerId=reader_id,
                url=error.url,
                status=error.status,
                body=error.body,
            )
            return f"Storage register failed. Status={error.status}. Body={error.body}", 502
        except Exception as error:
            Logger.error("device_register_failed", deviceId=device_id, readerId=reader_id, error=str(error))
            return "Internal server error", 500

        return "Successfully registered", 200

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
