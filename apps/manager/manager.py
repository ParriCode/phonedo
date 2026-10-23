from pathlib import Path
import os
import sys
import uuid
import time
import math
import atexit
import threading

import requests
from dotenv import load_dotenv
from flask import Flask, g, request , stream_with_context

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "libs"))

from logger import Logger
from pending_events import PendingEvents
from config import ManagerConfig
from server import ManagerServer
from client import ManagerClient, DeviceNotRegisteredError, InternalPostError

import os
import hashlib
import json
import hmac


def sign_event(message: dict) -> str:
    secret = os.getenv('MANAGER_PASSWORD')
    if not secret:
        raise RuntimeError('MANAGER_PASSWORD is not configured')
    value = dict(message['value'])
    value.pop('managerHash', None)
    envelope = {**message, 'value': value}
    encoded = json.dumps(envelope, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hmac.new(secret.encode('utf-8'), encoded, hashlib.sha256).hexdigest()




load_dotenv(Path(__file__).resolve().parent / "config.env")


def positive_setting(name, default, cast=float):
    value = cast(os.getenv(name, str(default)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return value


HTTP_TIMEOUT = positive_setting("MANAGER_HTTP_TIMEOUT_SECONDS", 10)
QUEUE_SIZE = positive_setting("MANAGER_QUEUE_SIZE", 1000, int)
RETRY_INTERVAL = positive_setting("MANAGER_RETRY_INTERVAL_SECONDS", 5)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


#Inicializar el entorno del logger
Logger.init(
    os.getenv("PHONENDO_LOGS_DIR", str(ROOT_DIR / "logs/services")),
    service="manager",
    verbose=env_bool("PHONENDO_VERBOSE", False),
    logging=env_bool("PHONENDO_LOGGING", True),
    dev=env_bool("PHONENDO_DEV", False),
)

app = Flask(__name__)
manager_config = ManagerConfig(os.getenv("MANAGER_CONFIG_PATH", str(Path(__file__).with_name("config.json"))))
manager_server = ManagerServer(app, manager_config)
manager_client = ManagerClient(manager_config, HTTP_TIMEOUT)
http_readers = set()
reader_source_lock = threading.Lock()
reader_locks = {}


def lock_for_reader(reader_id):
    with reader_source_lock:
        return reader_locks.setdefault(reader_id, threading.Lock())


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

#Obtener mensaje de una respuesta , si es un diccionario y tiene un campo message , se devuelve el valor de message
def get_message_from_response(response):
    if isinstance(response, dict) and isinstance(response.get("message"), dict):
        return response["message"]

    return response

#ok 
@app.get("/")
def alive():
    return "Service is alive"

#campos del newEvent
"""

    "token": self.token,
                "eventType": "observation",
                "payloadFormat": "text/turtle",
                "payload": ttl,
                "deviceId": device_id,
                "readerId": reader_id
"""
#Campo para el registro de un nuevo dispositivo (y reader)


#Se guarda el reader que realizó el registro , aunque loq ue realmente importa es el deviceId
"""

                "token": self.token,
                "readerId": reader_id,
                "deviceId": device.device_id,
                "deviceType":device.device_type,
                "creationDatetime": int(time.time() * 1000),
"""

#registrar dispositivol
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
        response = manager_client.register_device(message)

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


#registrar evento
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
    with lock_for_reader(reader_id):
        http_readers.add(reader_id)

    return submit_observation(body)


def submit_observation(body):
    device_id = body["deviceId"]
    reader_id = body["readerId"]
    payload = body["payload"]
    payload_format = body["payloadFormat"]
    event_type = body["eventType"]

    Logger.info("event_received", deviceId=device_id, readerId=reader_id, eventType=event_type)
    Logger.debug("event_payload_received", deviceId=device_id, readerId=reader_id, payload=payload)
    #construccion del mensaje
    message = {
        "key": str(uuid.uuid4()),
        "value": {
            "schemaVersion": "phonendo.event.v1",
            "eventType": "observation",
            "readerId": reader_id,
            "deviceId": device_id,
            "payloadFormat": payload_format,
            "payload": payload,
            "status": "Captured",
            "creationDatetime": int(time.time() * 1000),
        },
    }
    job = {"message": message, "stage": "lookup", "verified": None}
    return attempt_event(job, enqueue=True)


def on_reader_stream_event(body):
    if not isinstance(body, dict) or any(not body.get(field) for field in (
            "readerId", "deviceId", "payload", "payloadFormat", "eventType")):
        Logger.warning("reader_stream_invalid_event")
        return
    reader_id = body["readerId"]
    with lock_for_reader(reader_id):
        if reader_id in http_readers:
            Logger.debug("reader_stream_ignored_http_priority", readerId=reader_id)
            return
        submit_observation(body)




#Esta función procesa un evento por etapas,
# 1. Consulta el dispositivo en el storage para verificar que existe
# 2. Firma el evento con la clave secreta del manager
# 3. Envía el evento al verificador para su verificación
# 4. Si el verificador aprueba el evento, se almacena en el storage como verificado
# 5. Si alguna etapa falla, se maneja el error y se devuelve el estado correspondiente
def process_event(job):
    """Keep Captured in memory; persist only a positively verified event."""
    message = job["message"]
    if job["stage"] == "lookup":
        manager_client.get_device(message["value"]["deviceId"])
        job["stage"] = "signing"
    if job["stage"] == "signing":
        message["value"]["managerHash"] = sign_event(message)
        job["stage"] = "verification"
    if job["stage"] == "verification":
        manager_server.publish_captured(message)
        response = manager_client.verify_event(message)
        if isinstance(response, dict) and response.get("verified") is False:
            raise EventRejected("Verifier rejected event")
        verified = get_message_from_response(response)
        if (not isinstance(response, dict) or response.get("verified") is not True
                or not isinstance(verified, dict)
                or verified.get("key") != message["key"]
                or not isinstance(verified.get("value"), dict)
                or verified["value"].get("status") != "Verified"
                or not verified["value"].get("verifierSign")):
            raise RuntimeError("Invalid verification response")
        job["verified"] = verified
        job["stage"] = "store_verified"
    manager_server.publish_verified(job["verified"])
    stored = manager_client.store_event(job["verified"])
    if get_message_from_response(stored) != job["verified"]:
        raise RuntimeError("Storage did not confirm the verified message")
    Logger.info("event_stored_as_verified", eventId=message["key"])


class EventRejected(RuntimeError):
    pass


def attempt_event(job, *, enqueue):
    event_id = job["message"]["key"]
    try:
        process_event(job)
        return {"eventId": event_id, "status": "Verified"}, 200
    except requests.Timeout:
        if enqueue:
            pending_events.put(job)
        Logger.warning("event_pending_timeout", eventId=event_id, stage=job["stage"])
        return {"eventId": event_id, "status": "Pending", "stage": job["stage"]}, 202
    except Exception as error:
        rejected = isinstance(error, EventRejected) or (
            job["stage"] == "verification" and isinstance(error, InternalPostError)
            and error.status in (400, 422))
        status = 422 if rejected else (404 if isinstance(error, DeviceNotRegisteredError)
                                     else 500 if job["stage"] == "signing" else 502)
        Logger.warning("event_discarded" if rejected else "event_processing_failed",
                       eventId=event_id, stage=job["stage"], error=str(error))
        return {"eventId": event_id, "status": "Rejected" if rejected else "Failed",
                "stage": job["stage"]}, status


def retry_event(job):
    _, status = attempt_event(job, enqueue=False)
    return status == 202


def queue_discarded(job):
    Logger.warning("event_discarded_queue_full", eventId=job["message"]["key"],
                   stage=job["stage"])


pending_events = PendingEvents(QUEUE_SIZE, RETRY_INTERVAL, retry_event, queue_discarded)
atexit.register(pending_events.close)
stop_reader_streams = manager_client.start_reader_streams(on_reader_stream_event)
atexit.register(stop_reader_streams)


if __name__ == "__main__":
    Logger.info("service_starting", port=os.getenv("PORT_MANAGER"))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT_MANAGER")))
