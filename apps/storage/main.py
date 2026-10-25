import os
import sys
import time
from pathlib import Path

from flask import Flask, g, jsonify, request
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import PhonendoDB
from storage_support.config import StorageConfig
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
http_clients = set()


@app.get('/info')
def info():
    return ([{'peer': peer, 'transport': 'http'} for peer in sorted(http_clients)]
            + [{'peer': url.rsplit('/stream', 1)[0], 'transport': 'sse'}
               for url in sorted(manager_subscriptions.connected)]
            + [{'peer': peer, 'transport': 'sse'} for peer in stored_stream.peers()])


@app.get('/logs')
def logs():
    return list(Logger.instance().messages)


storage_config = StorageConfig()
my_db = PhonendoDB(storage_config.database_path)
from storage_support.event_stream import EventStream
from storage_support.server_stream import stream_response
stored_stream = EventStream()
if storage_config.stream_enabled:
    app.add_url_rule('/stream', 'stream', lambda: stream_response(stored_stream, storage_config.token))

def write_event(message):
    my_db.write(message['key'], message['value'])
    if storage_config.stream_enabled:
        stored_stream.publish(message)


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
    if request.path in ('/info', '/logs'):
        return response
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


@app.get("/")
def home():
    data = my_db.read_all()
    return jsonify(data), 200


@app.post("/events")
def store_event():
    try:
        Logger.debug("storage_event_received", body=sanitize_body(request.json))

        if not request.json.get("token") or request.json.get("token") != storage_config.token:
            Logger.warning("storage_event_not_authorized")
            return "Not authorized", 401

        if not request.json.get("message"):
            Logger.warning("storage_event_bad_request")
            return "Bad request", 403

        message = request.json["message"]
        http_clients.add(request.remote_addr or 'unknown')

        write_event(message)

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



def consume_manager_event(message):
    if (not isinstance(message, dict) or not isinstance(message.get('key'), str)
            or not isinstance(message.get('value'), dict)
            or message['value'].get('status') != 'Verified'
            or not message['value'].get('verifierSign')):
        Logger.warning('storage_stream_invalid_event')
        return
    write_event(message)


from storage_support.stream_client import StreamClient
import atexit
manager_targets = []
if storage_config.manager_subscriptions:
    for target in storage_config.manager_subscriptions:
        target = {'url': target} if isinstance(target, str) else dict(target)
        target['url'] = target['url'].rstrip('/') + '/stream/storage'
        manager_targets.append(target)
manager_subscriptions = StreamClient(manager_targets, storage_config.token, consume_manager_event,
                                     service_url=storage_config.public_url)
manager_subscriptions.start()
atexit.register(manager_subscriptions.close)

def start():
    Logger.info("service_starting", port=os.getenv("PORT_STORAGE", 5000))
    app.run(host=storage_config.host, port=storage_config.port)


if __name__ == "__main__":
    start()
