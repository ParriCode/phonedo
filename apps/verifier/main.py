import os
import sys
import json
import time
import hmac
import hashlib
from pathlib import Path
from uuid import UUID

from flask import Flask, g, request, jsonify
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "libs"))

from logger import Logger


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def is_uuid4(value: str) -> bool:
    try:
        uuid_obj = UUID(str(value), version=4)
    except (ValueError, TypeError, AttributeError):
        return False

    return str(uuid_obj) == str(value).lower()


def canonical_json(data) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    )


def is_sha256_hex(value: str) -> bool:
    if not isinstance(value, str):
        return False

    if len(value) != 64:
        return False

    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def is_milliseconds_timestamp(value) -> bool:
    if isinstance(value, bool):
        return False

    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def is_non_empty_string(value) -> bool:
    return isinstance(value, str) and bool(value.strip())



def sign_with_verifier(message: dict) -> str:
    message_bytes = canonical_json(message).encode("utf-8")

    return private_key.sign(
        message_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    ).hex()


load_dotenv(Path(__file__).resolve().parent / "config.env")

Logger.init(
    os.getenv("PHONENDO_LOGS_DIR", str(ROOT_DIR / "logs/services")),
    service="verifier",
    verbose=env_bool("PHONENDO_VERBOSE", False),
    logging=env_bool("PHONENDO_LOGGING", True),
    dev=env_bool("PHONENDO_DEV", False),
)

BASE_DIR = Path(__file__).resolve().parent
KEYS_PATH = BASE_DIR / "keys.json"

with open(KEYS_PATH, "r", encoding="utf-8") as f:
    keys = json.load(f)

private_key = serialization.load_pem_private_key(
    keys["privateKey"].encode("utf-8"),
    password=None
)

app = Flask(__name__)


def sanitize_body(body):
    if not isinstance(body, dict):
        return body

    sanitized = dict(body)
    sanitized.pop("token", None)

    message = sanitized.get("message")
    if isinstance(message, dict):
        sanitized["message"] = {
            "key": message.get("key"),
            "value": {
                "deviceId": (message.get("value") or {}).get("deviceId")
                if isinstance(message.get("value"), dict)
                else None,
                "readerId": (message.get("value") or {}).get("readerId")
                if isinstance(message.get("value"), dict)
                else None,
                "status": (message.get("value") or {}).get("status")
                if isinstance(message.get("value"), dict)
                else None,
            },
        }

    return sanitized


@app.before_request
def start_request_log():
    g.request_started_at = time.time()


@app.after_request
def log_request(response):
    duration_ms = int((time.time() - g.get("request_started_at", time.time())) * 1000)
    body = request.get_json(silent=True) or {}
    message = body.get("message") if isinstance(body, dict) else None
    value = message.get("value") if isinstance(message, dict) else None

    Logger.request(
        request.method,
        request.path,
        response.status_code,
        durationMs=duration_ms,
        eventId=message.get("key") if isinstance(message, dict) else None,
        deviceId=value.get("deviceId") if isinstance(value, dict) else None,
        readerId=value.get("readerId") if isinstance(value, dict) else None,
    )
    Logger.debug("request_body", body=sanitize_body(body))
    return response


@app.get("/")
def healthcheck():
    return "Service is alive", 200


@app.post("/verify")
def verify():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        Logger.warning("verify_invalid_json")
        return jsonify({"verified": False, "error": "Invalid JSON body"}), 400

    token = data.get("token")
    expected_token = os.getenv("API_TOKEN_VERIFIER")

    if not expected_token:
        Logger.error("verifier_token_not_configured")
        return jsonify({"verified": False, "error": "API_TOKEN_VERIFIER is not configured"}), 500
    
    #Esta comparación es para que tarde lo mismo la comparación del token , ya que sino el atacante podría medir tiempos y 
    #tratar de averiguar el token poco a poco
    if not token or not hmac.compare_digest(str(token), expected_token):
        Logger.warning("verify_not_authorized")
        return jsonify({"verified": False, "error": "Not authorized"}), 401

    message = data.get("message")

    if not isinstance(message, dict):
        Logger.warning("verify_bad_request", error="message is required and must be an object")
        return jsonify({"verified": False, "error": "message is required and must be an object"}), 400


    #En lugar de mandar el error nada más producirse, acumularlos , es mejor así porque se tiene la lista completa
    errors = []

    key = message.get("key")
    value = message.get("value")

    if not key:
        errors.append("key does not exist")
    elif not is_uuid4(key):
        errors.append("key is not a valid UUID4")

    if not isinstance(value, dict):
        errors.append("value does not exist or is not an object")

    if errors:
        Logger.warning("verify_rejected_bad_envelope", errors=errors)
        return jsonify({"verified": False, "errors": errors}), 400

    schema_version = value.get("schemaVersion")
    event_type = value.get("eventType")
    reader_id = value.get("readerId")
    device_id = value.get("deviceId")
    payload_format = value.get("payloadFormat")
    payload = value.get("payload")
    status = value.get("status")
    creation_datetime = value.get("creationDatetime")
    manager_hash = value.get("managerHash")

    if not schema_version:
        errors.append("schemaVersion does not exist")

    if not event_type:
        errors.append("eventType does not exist")

    if not reader_id:
        errors.append("readerId does not exist")

    if not device_id:
        errors.append("deviceId does not exist")

    if not payload_format:
        errors.append("payloadFormat does not exist")

    if payload is None:
        errors.append("payload does not exist")

    if not status:
        errors.append("status does not exist")

    if creation_datetime is None:
        errors.append("creationDatetime does not exist")

    if not manager_hash:
        errors.append("managerHash does not exist")
    #Enviar todos los correos
    if errors:
        Logger.warning("verify_rejected_missing_fields", eventId=key, errors=errors)
        return jsonify({"verified": False, "errors": errors}), 400

    #Estos son campos que el maanager siempre debería de mandar igual

    if schema_version != "phonendo.event.v1":
        errors.append("schemaVersion is not valid")

    if event_type != "observation":
        errors.append("eventType is not valid")

    if status != "Captured":
        errors.append("status must be Captured")

    # Formato
    if reader_id is None or reader_id == "":
        errors.append("readerId is not a valid UUID4")

    if not is_non_empty_string(device_id):
        errors.append("deviceId must be a non-empty string")

    if not isinstance(payload_format, str) or not payload_format.strip():
        errors.append("payloadFormat must be a non-empty string")

    if payload_format == "text/turtle":
        if not is_non_empty_string(payload):
            errors.append("payload must be a non-empty Turtle string")
    elif not isinstance(payload, dict):
        errors.append("payload must be a JSON object")
    elif not payload:
        errors.append("payload cannot be empty")

    if isinstance(payload, dict):
        try:
            canonical_json(payload)
        except (TypeError, ValueError):
            errors.append("payload is not JSON serializable")

    if not is_milliseconds_timestamp(creation_datetime):
        errors.append("creationDatetime must be a milliseconds timestamp")

    if not is_sha256_hex(manager_hash):
        errors.append("managerHash must be a SHA256 hex string")

    if errors:
        Logger.warning("verify_rejected_invalid_fields", eventId=key, deviceId=device_id, readerId=reader_id, errors=errors)
        return jsonify({
            "verified": False,
            "status": "Rejected",
            "errors": errors
        }), 422

    creation_datetime = int(creation_datetime)
    now_ms = int(time.time() * 1000)

    max_age_ms = int(os.getenv("MAX_EVENT_AGE_MS", 5 * 60 * 1000))
    max_future_drift_ms = int(os.getenv("MAX_FUTURE_DRIFT_MS", 30 * 1000))

    # Tiempo
    if creation_datetime > now_ms + max_future_drift_ms:
        errors.append("creationDatetime cannot be in the future")

    if creation_datetime < now_ms - max_age_ms:
        errors.append("creationDatetime is too old")

    # Hash del Manager
  


    if errors:
        Logger.warning("verify_rejected_invalid_time", eventId=key, deviceId=device_id, readerId=reader_id, errors=errors)
        return jsonify({
            "verified": False,
            "status": "Rejected",
            "errors": errors
        }), 422

    # Documento verificado
    verified_message = {
        "key": key,
        "value": {
            "schemaVersion": schema_version,
            "eventType": event_type,
            "readerId": reader_id,
            "deviceId": device_id,
            "payloadFormat": payload_format,
            "payload": payload,
            "status": "Verified",
            "creationDatetime": creation_datetime,
            "managerHash": manager_hash,
            "verifierSignDatetime": now_ms,
        }
    }

    signature = sign_with_verifier(verified_message)

    verified_message["value"]["verifierSign"] = signature

    Logger.info("event_verified", eventId=key, deviceId=device_id, readerId=reader_id)
    Logger.debug("event_signature", eventId=key, signature=signature)

    return jsonify({
        "verified": True,
        "status": "Verified",
        "message": verified_message
    }), 200


if __name__ == "__main__":
    Logger.info("service_starting", port=os.getenv("PORT_VERIFIER", 5000))
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT_VERIFIER", 5000))
    )
