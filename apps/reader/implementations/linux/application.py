"""Linux composition root: configuration, logging, sources and transports."""
import os
from pathlib import Path
from logger import Logger
from reader_core import ReaderCore, Observation
from reader_server import ReaderService, ReaderRuntime
from reader_server.stream import ObservationStream, StreamOutput
from .config import config_bool, load_config, load_env, load_devices_from_config
from .sources import build_sources
from .communication.manager_client import ManagerClient
from .communication.manager_output import ManagerOutput

READER_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = READER_DIR.parents[1]

class LinuxReader:
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
        self.env = {**load_env(READER_DIR / "config.env"),
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
        )
        outputs = [StreamOutput(self.stream)]
        if self.manager_output:
            outputs.append(self.manager_output)
        self.service = ReaderService(self.core, tuple(outputs))
        load_devices_from_config(self.core, config, default_device_id=config.get("default_device_id"))
        self.sources = build_sources(config, self.ingest)
        self.serial_manager = next((s for s in self.sources
                                    if type(s).__name__ == "SerialSource"), None)
        self.bluetooth_manager = next((s for s in self.sources
                                       if type(s).__name__ == "BluetoothSource"), None)
        self.server = None
        if config_bool(server, "enabled", False):
            from .communication.http_server import AiohttpReaderServer
            self.server = AiohttpReaderServer(
                self.service, self.stream,
                host=server.get("host", "127.0.0.1"),
                port=server.get("port", 3002),
                token=server.get("token", self.env.get("API_TOKEN_READER", "")),
                stream_enabled=config_bool(server, "stream_enabled", True),
            )


    def ingest(self, observation: Observation) -> bool:
        return self.service.ingest(observation)

    async def run(self):
        Logger.info("service_starting", readerId=self.reader_id)
        runtime = ReaderRuntime(
            sources=self.sources,
            servers=[self.server] if self.server else [],
            workers=[self.manager_output] if self.manager_output else [],
            on_close=self.stream.close,
        )
        await runtime.run()
