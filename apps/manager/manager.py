"""Compose and run the Manager service."""
from pathlib import Path
import os
import sys
import math
import atexit
from dotenv import load_dotenv
from flask import Flask
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "libs"))
from logger import Logger
from config import ManagerConfig
from client import ManagerClient
from server import ManagerServer, register_routes
from core import ManagerCore

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
manager_client = ManagerClient(manager_config, HTTP_TIMEOUT)
manager_server = ManagerServer(app, manager_config)
core = ManagerCore(manager_client, manager_server, QUEUE_SIZE, RETRY_INTERVAL)
register_routes(app, core)
atexit.register(core.close)

if __name__ == "__main__":
    stop_streams = manager_client.start_reader_streams(core.on_reader_stream_event)
    try:
        app.run(host="0.0.0.0", port=manager_config.port)
    finally:
        stop_streams()
        core.close()
