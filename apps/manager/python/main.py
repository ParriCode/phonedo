from pathlib import Path
import os
import sys
import uuid
import hashlib
import time

import requests
from dotenv import load_dotenv
from flask import Flask, g, request

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR / "libs/python"))

from logger import Logger

load_dotenv(Path(__file__).resolve().parent.parent / "config.env")


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


def sanitize_body(body):
    if not isinstance(body, dict):
        return body

    sanitized = dict(body)
    sanitized.pop("token", None)

    if "payload" in sanitized:
        sanitized["payload"] = "<payload>"

    return sanitized


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
    Logger.debug("request_body", body=sanitize_body(body))
    return response


def get_device_from_storage(device_id: str) -> dict:
    url = f"{os.getenv('INTERNAL_URL_STORAGE_DEVICES')}/{device_id}"
    Logger.debug("storage_device_lookup_request", url=url, deviceId=device_id)

    response = requests.get(
        url,
        headers={
            "X-Storage-Token": os.getenv("API_TOKEN_STORAGE")
        },
        timeout=5
    )

    if response.status_code == 404:
        Logger.warning("storage_device_not_registered", deviceId=device_id)
        raise ValueError("Device not registered")

    if response.status_code != 200:
        Logger.error(
            "storage_device_lookup_failed",
            deviceId=device_id,
            status=response.status_code,
            body=response.text,
        )
        raise RuntimeError(f"Storage error: {response.status_code} {response.text}")

    Logger.info("storage_device_found", deviceId=device_id)
    return response.json()["value"]

def generate_wearable_key(mac_address : str ) -> str: 
    manager_password = os.getenv("MANAGER_PASSWORD")
    if not manager_password:
        raise ValueError("MANAGER_PASSSWORD no está definida")

    #normalizar la MAC
    mac_lower = mac_address.strip().lower()
    clave = f"{mac_lower}:{manager_password}"

    hash_sha265 = hashlib.sha256(clave.encode("utf-8")).hexdigest()

    return hash_sha265


def get_message_from_response(response):
    if isinstance(response, dict) and isinstance(response.get("message"), dict):
        return response["message"]

    return response

def post_request(url, body):
    Logger.debug("internal_post_request", url=url, body=sanitize_body(body))
    response = requests.post(url, json=body, timeout=10)
    Logger.debug("internal_post_response", url=url, status=response.status_code, body=response.text)
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return response.text


def to_bytes(string):
    return list(string.encode("utf-8"))


def sign_data_source(message):
    hash_value = hashlib.sha256(
        (message["value"]["device"] + "Phonendo").encode("utf-8")
    ).hexdigest()

    bytes_value = to_bytes(hash_value)
    return message



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
    mac_address         = body.get("macAddress")
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

    if not mac_address:
        Logger.warning("manager_register_device_bad_request", missing="macAddress")
        return {"error": "macAddress is required"}, 400
    
    if not creation_date_time:
        Logger.warning("manager_register_device_bad_request", missing="creationDatetime")
        return {"error": "creation_date_time is requires"}, 400 
    

    Logger.info("device_register_received", deviceId=device_id, readerId=reader_id)

    message = {
        "key": device_id,
        "value": {
            "deviceId": device_id,
            "deviceType": device_type,
            "macAddress":mac_address,
            "registeredByReader": reader_id,
            "registrationDatetime": int(time.time() * 1000),
        },
    }

    try:
        hash_sha256 =  generate_wearable_key(mac_address)
        message["value"]["managerHash"] = hash_sha256
        #Registro de un nuevo token
        storage_body = {
            "token": os.getenv("API_TOKEN_STORAGE"),
            "message":message
        }
        #meter en el stotage
        response = post_request(os.getenv("INTERNAL_URL_STORAGE_REGISTER_DEVICES"), storage_body)

        Logger.info("device_registered", deviceId=device_id, readerId=reader_id)
        Logger.debug("device_register_storage_response", response=response)
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
    try:
        device = get_device_from_storage(device_id)
    except Exception as error:
        Logger.warning("event_rejected_device_not_registered", deviceId=device_id, readerId=reader_id, error=str(error))
        return "device not registered " , 404


    mac_address = device.get("macAddress")

    if not mac_address:
        raise ValueError("Device does not have macAddress")

    manager_signature = generate_wearable_key(mac_address)

    message["value"]["managerHash"] = manager_signature

    try:
        request_body = {
            "token": os.getenv("API_TOKEN_STORAGE"),
            "message": message,
        }

        stored_message = post_request(
            os.getenv("INTERNAL_URL_STORAGE_EVENTS"),
            request_body,
        )
        Logger.info("event_stored_as_captured", eventId=message["key"], deviceId=device_id, readerId=reader_id)

        request_body["message"] = get_message_from_response(stored_message)
        request_body["token"] = os.getenv("API_TOKEN_VERIFIER")

        verified_response = post_request(
            os.getenv("INTERNAL_URL_VERIFIER_VERIFY"),
            request_body,
        )
        Logger.info("event_verified", eventId=message["key"], deviceId=device_id, readerId=reader_id)

        request_body["message"] = get_message_from_response(verified_response)
        request_body["token"] = os.getenv("API_TOKEN_STORAGE")

        stored_verified_message = post_request(
            os.getenv("INTERNAL_URL_STORAGE_EVENTS"),
            request_body,
        )
        Logger.info("event_stored_as_verified", eventId=message["key"], deviceId=device_id, readerId=reader_id)

        request_body["message"] = stored_verified_message
        request_body["token"] = os.getenv("API_TOKEN_PUBLISHER")

        # published_message = post_request(
        #     os.getenv("INTERNAL_URL_PUBLISHER_PUBLISH"),
        #     request_body,
        # )

        request_body["token"] = os.getenv("API_TOKEN_STORAGE")

        # delete_request(
        #     os.getenv("INTERNAL_URL_STORAGE_EVENTS") + "/" + published_message["key"],
        #     request_body,
        # )

    except Exception as error:
        Logger.error("event_processing_failed", deviceId=device_id, readerId=reader_id, error=str(error))

    return "Event accepted", 200


if __name__ == "__main__":
    Logger.info("service_starting", port=os.getenv("PORT_MANAGER"))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT_MANAGER")))
