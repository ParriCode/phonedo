import os
import sys
import time
from pathlib import Path

from flask import Flask, g, jsonify, request
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import PhonendoDB
from storage_support.logger import Logger

load_dotenv(Path(__file__).resolve().parent / "config.env")


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


Logger.init(
    os.getenv("PHONENDO_LOGS_DIR", str(ROOT_DIR / "logs/services")),
    service="storage",
    verbose=env_bool("PHONENDO_VERBOSE", False),
    logging=env_bool("PHONENDO_LOGGING", True),
    dev=env_bool("PHONENDO_DEV", False),
)

app = Flask(__name__)


my_db  = PhonendoDB()


def sanitize_body(body):
    if not isinstance(body, dict):
        return body

    sanitized = dict(body)
    sanitized.pop("token", None)
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
        deviceId=(value or {}).get("deviceId") if isinstance(value, dict) else None,
    )
    Logger.debug("request_body", body=sanitize_body(body))
    return response


def storage_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()

    return (
        request.headers.get("X-Storage-Token")
        or request.headers.get("token")
        or request.headers.get("Token")
    )

@app.get("/")
def home():
    data = my_db.read_all()
    return jsonify(data), 200


@app.post("/registerDevice")
def store_device():
    try:
        Logger.debug("device_received", body=sanitize_body(request.json))
        #checkear el token
        if not request.json.get("token") or request.json.get("token") != os.getenv("API_TOKEN_STORAGE"):
            Logger.warning("storage_device_register_not_authorized")
            return "Not authorized", 401

        if not request.json.get("message"):
            Logger.warning("storage_device_register_bad_request")
            return "Bad request", 403
        #Obtener el mensaje
        message = request.json["message"]
        Logger.debug("storage_device_register_message", storedMessage=message)

        my_db.write(message["key"], message["value"])

        Logger.info("device_registered", deviceId=message["key"])
        return jsonify(message), 200

    except Exception as error:
        Logger.error("storage_device_register_failed", error=str(error))
        return "Internal server error", 500


@app.get("/devices/<device_id>")
def get_device(device_id):
    try:

        Logger.debug("storage_device_lookup", deviceId=device_id)

        token = storage_token_from_request()

        if not token or token != os.getenv("API_TOKEN_STORAGE"):
            Logger.warning("storage_device_lookup_not_authorized", deviceId=device_id)
            return jsonify({"error": "Not authorized"}), 401

        device = my_db.read(device_id)

        Logger.debug("storage_device_lookup_result", deviceId=device_id, found=bool(device))


        if not device:
            Logger.warning("device_not_found", deviceId=device_id)
            return jsonify({"error": "Device not found"}), 404

        Logger.info("device_found", deviceId=device_id)
        return jsonify({
            "key": device_id,
            "value": device
        }), 200

    except Exception as error:
        Logger.error("storage_device_lookup_failed", deviceId=device_id, error=str(error))
        return jsonify({"error": "Internal server error"}), 500


@app.post("/events")
def store_event():
    try:
        Logger.debug("storage_event_received", body=sanitize_body(request.json))

        if not request.json.get("token") or request.json.get("token") != os.getenv("API_TOKEN_STORAGE"):
            Logger.warning("storage_event_not_authorized")
            return "Not authorized", 401

        if not request.json.get("message"):
            Logger.warning("storage_event_bad_request")
            return "Bad request", 403

        message = request.json["message"]

        my_db.write(message["key"], message["value"])

        Logger.info(
            "event_stored",
            eventId=message["key"],
            deviceId=message.get("value", {}).get("deviceId") if isinstance(message.get("value"), dict) else None,
        )

        return jsonify(message), 200

    except Exception as error:
        Logger.error("storage_event_failed", error=str(error))
        return "Internal server error", 500


@app.get("/raw")
def raw():
    try:
        data = my_db.read_all()
        Logger.info("storage_raw_read", items=len(data) if hasattr(data, "__len__") else None)
        return jsonify(data), 200
    except Exception as error:
        Logger.error("storage_raw_read_failed", error=str(error))
        return "Internal server error", 500


def start():
    Logger.info("service_starting", port=os.getenv("PORT_STORAGE", 5000))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT_STORAGE", 5000)))


if __name__ == "__main__":
    start()
