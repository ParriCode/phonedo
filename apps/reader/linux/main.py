from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR / "libs"))
sys.path.insert(0, str(ROOT_DIR / "apps/reader/core/python"))
sys.path.insert(0, str(ROOT_DIR / "apps/reader"))

from logger import Logger
from reader_core.core import ReaderCore
from reader_core.observation import Observation
from linux.config import config_bool, load_config, load_env
from linux.sources import build_sources
from linux.communication.manager_client import ManagerClient
from linux.communication.manager_output import ManagerOutput
from linux.communication.stream import ObservationStream


class Reader:
    """Compose acquisition sources, the data model, and optional transports."""

    def __init__(self, id: str | None = None,
                 config_file: str = "devices_and_sensors.json",
                 verbose: bool | None = None, static: bool = False):
        self.config_file = config_file
        path = Path(config_file)
        if not path.is_absolute() and not path.exists():
            path = Path(__file__).resolve().parent / path
        config = load_config(path)
        self.config = config
        self.env = {**load_env(Path(__file__).resolve().parent.parent / "config.env"),
                    **os.environ}
        self.reader_id = id or config.get("reader_id") or "reader"
        self.static = static or config_bool(config, "static", False)
        config = {**config, "static": self.static}
        Logger.init(
            self.env.get("PHONENDO_LOGS_DIR", str(ROOT_DIR / "logs/services")),
            service="reader",
            verbose=verbose if verbose is not None else config_bool(self.env, "PHONENDO_VERBOSE", False),
            logging=config_bool(self.env, "PHONENDO_LOGGING", True),
            dev=config_bool(self.env, "PHONENDO_DEV", False),
        )
        communication = config.get("communication", {})
        # Without this block preserve legacy delivery; otherwise opt in.
        legacy = "communication" not in config
        manager = communication.get("manager", {})
        server = communication.get("server", {})
        self.stream = ObservationStream(server.get("queue_size", 256))
        self.manager_client = None
        self.manager_output = None
        if config_bool(manager, "enabled", legacy):
            self.manager_client = ManagerClient(
                base_url=manager.get("url") or self.env.get("INTERNAL_URL_MANAGER")
                         or "http://127.0.0.1:3003",
                token=manager.get("token", self.env.get("API_TOKEN_MANAGER", "token_manager")),
                timeout_seconds=manager.get("timeout_seconds", 10),
            )
            self.manager_output = ManagerOutput(
                self.manager_client,
                register=config_bool(manager, "register_devices", True),
                send=config_bool(manager, "send_observations", True),
                queue_size=manager.get("queue_size", 256),
            )
        self.core = ReaderCore(
            reader_id=self.reader_id,
            allow_new_devices=not self.static,
            allow_new_sensors=not self.static,
            on_register_device=(self.manager_output.register_device
                                if self.manager_output else None),
            on_send=self.publish,
        )
        self.core.load_devices_from_config(config, default_device_id=self.reader_id)
        self.sources = build_sources(config, self.handle_measurement_data)
        self.serial_manager = next((s for s in self.sources
                                    if type(s).__name__ == "SerialSource"), None)
        self.bluetooth_manager = next((s for s in self.sources
                                       if type(s).__name__ == "BluetoothSource"), None)
        self.server = None
        if config_bool(server, "enabled", False):
            from linux.communication.server import ReaderServer
            self.server = ReaderServer(
                self.core, self.stream,
                host=server.get("host", "127.0.0.1"),
                port=server.get("port", 3002),
                token=server.get("token", self.env.get("API_TOKEN_READER", "")),
                stream_enabled=config_bool(server, "stream_enabled", True),
            )

    def publish(self, observation_payload, reader_id, device_id):
        self.stream.publish({
            "eventType": "observation", "readerId": reader_id,
            "deviceId": device_id, "payloadFormat": "application/json", "payload": observation_payload,
        })
        if self.manager_output:
            self.manager_output.publish(observation_payload, reader_id, device_id)

    def handle_measurement_data(self, observation: Observation) -> bool:
        return self.core.handle_measurement_data(observation)

    handle_bluetooth_data = handle_measurement_data
    handle_serial_data = handle_measurement_data

    async def run(self):
        if not self.sources and self.server is None:
            raise RuntimeError("No hay fuentes ni servidor activos.")
        Logger.info("service_starting", readerId=self.reader_id)
        tasks = []
        try:
            if self.server:
                await self.server.start()
            if self.manager_output:
                tasks.append(asyncio.create_task(self.manager_output.run()))
            tasks.extend(asyncio.create_task(source.start()) for source in self.sources)
            if tasks:
                await asyncio.gather(*tasks)
            else:
                await asyncio.Event().wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.gather(*(source.stop() for source in self.sources),
                                 return_exceptions=True)
            self.stream.close()
            if self.server:
                await self.server.stop()


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
    reader = Reader(
        id=args.reader_id,
        config_file=args.config,
        verbose=args.verbose,
        static=args.static
    )
    asyncio.run(reader.run())
