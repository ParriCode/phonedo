"""Linux command-line entry point; paths are configured only at startup."""
import argparse
import asyncio
import sys
from pathlib import Path

READER_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = READER_DIR.parents[1]
for path in (ROOT_DIR / "libs", READER_DIR, READER_DIR / "core/python", READER_DIR / "server/python"):
    sys.path.insert(0, str(path))

import os
from dataclasses import dataclass
from logger import Logger
from reader_core import ReaderCore
from reader_server import ReaderRuntime, ReaderServer, ServerConfig
from reader_server.contracts import Source
from implementations.linux.config import config_bool, load_config, load_env, load_devices_from_config
from implementations.linux.sources import build_sources
from implementations.linux.communication.manager_client import ManagerClient
from implementations.linux.communication.manager_output import ManagerOutput


@dataclass
class LinuxReaderSettings:
    reader_id: str
    config: dict
    env: dict[str, str]
    static: bool
    verbose: bool | None


@dataclass
class LinuxReaderApp:
    core: ReaderCore
    server: ReaderServer
    sources: list[Source]
    manager_output: ManagerOutput | None


def load_settings(args):
    path = Path(args.config)
    if not path.is_absolute() and not path.exists():
        path = Path(__file__).resolve().parent / path
    config = load_config(path)
    static = args.static or config_bool(config, "static", False)
    return LinuxReaderSettings(
        reader_id=args.reader_id or config.get("reader_id") or "reader",
        config={**config, "static": static},
        env={**load_env(READER_DIR / "config.env"), **os.environ},
        static=static, verbose=args.verbose,
    )


def build_app(settings):
    """Compose the core, server and platform adapters explicitly."""
    config = settings.config
    verbose = settings.verbose
    Logger.init(
        settings.env.get("PHONENDO_LOGS_DIR", str(ROOT_DIR / "logs/services")),
        service="reader",
        verbose=verbose if verbose is not None else config_bool(settings.env, "PHONENDO_VERBOSE", False),
        logging=config_bool(settings.env, "PHONENDO_LOGGING", True),
        dev=config_bool(settings.env, "PHONENDO_DEV", False),
    )
    communication = config.get("communication", {})
    # Without this block preserve legacy delivery; otherwise opt in.
    legacy = "communication" not in config
    manager = communication.get("manager", {})
    server_settings = communication.get("server", {})
    manager_output = None
    if config_bool(manager, "enabled", legacy):
        manager_client = ManagerClient(
            base_url=manager.get("url") or settings.env.get("INTERNAL_URL_MANAGER")
                     or "http://127.0.0.1:3003",
            token=manager.get("token", settings.env.get("API_TOKEN_MANAGER", "token_manager")),
            timeout_seconds=manager.get("timeout_seconds", 10),
        )
        manager_output = ManagerOutput(
            manager_client,
            register=config_bool(manager, "register_devices", True),
            send=config_bool(manager, "send_observations", True),
            queue_size=manager.get("queue_size", 256),
        )
    core = ReaderCore(
        settings.reader_id, allow_new_devices=not settings.static,
        allow_new_sensors=not settings.static,
    )
    server = ReaderServer(
        core,
        config=ServerConfig(
            enabled=config_bool(server_settings, "enabled", False),
            host=server_settings.get("host", "127.0.0.1"), port=server_settings.get("port", 3002),
            token=server_settings.get("token", settings.env.get("API_TOKEN_READER", "")),
            stream_enabled=config_bool(server_settings, "stream_enabled", True),
            queue_size=server_settings.get("queue_size", 256),
        ),
        outputs=(manager_output,) if manager_output else (),
    )
    # Attach outputs before registration so configured devices reach the manager.
    load_devices_from_config(core, config, default_device_id=config.get("default_device_id"))
    sources = build_sources(config, core.ingest)
    return LinuxReaderApp(core, server, sources, manager_output)


async def run_app(app):
    Logger.info("service_starting", readerId=app.core.reader_id)
    runtime = ReaderRuntime(
        sources=app.sources,
        servers=[app.server] if app.server.config.enabled else [],
        workers=[app.manager_output] if app.manager_output else [],
    )
    try:
        await runtime.run()
    finally:
        # Also dispose the local stream when HTTP is disabled.
        await app.server.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phonendo Python Reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Qué hace:
  - Carga dispositivos y sensores desde devices_and_sensors.json.
  - Escucha puertos serie configurados, incluidos RFCOMM expuestos como /dev/rfcomm*.
  - Acepta mensajes serie en JSON, sensor:valor o valor plano.
  - Completa valores planos con la configuración del puerto y del sensor.
  - Convierte cada medición en una observación JSON.
  - Publica por stream y/o envía al Manager según communication.

Configuración de conflictos:
  - En devices[] y sensors[] se puede poner "allow_conflicts": true o false.
  - Si es false y un mensaje contradice la configuración, la medición se descarta.
  - Si es true, el dato recibido puede crear/usar el nuevo device o sensor recibido.

Ejemplos:
  python3 main.py
  python3 main.py --config devices_and_sensors.json
  python3 main.py --reader-id reader-1
""",
    )
    parser.add_argument("--reader-id", dest="reader_id", default=None, help="Identificador lógico del Reader. Por defecto usa reader_id del JSON o 'reader'.")
    parser.add_argument("--config", default="devices_and_sensors.json", help="Ruta al JSON de configuración de dispositivos, sensores y comunicaciones.")
    parser.add_argument("--verbose", action="store_true", default=None, help="Habilitar salida detallada para depuración.")
    parser.add_argument("--static", action="store_true", help="No descubrir dispositivos o sensores fuera de la configuración.")
    return parser.parse_args()



if __name__ == "__main__":
    args = parse_args()
    settings = load_settings(args)
    app = build_app(settings)
    asyncio.run(run_app(app))
