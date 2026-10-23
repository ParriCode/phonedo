import json
import os
from pathlib import Path


class ManagerConfig:
    """Configuration for the Phonendo Manager service."""

    def __init__(self, config_path: str | Path):

        # ---------------------------------------------------------
        # Manager
        # ---------------------------------------------------------

        self.port = int(os.getenv("PORT_MANAGER", "3003"))

        self.password = os.getenv("MANAGER_PASSWORD")

        if not self.password:
            raise RuntimeError("MANAGER_PASSWORD is not configured")

        # ---------------------------------------------------------
        # API tokens
        # ---------------------------------------------------------

        self.api_token_manager = os.getenv("API_TOKEN_MANAGER")
        self.api_token_reader = os.getenv("API_TOKEN_READER")
        self.api_token_storage = os.getenv("API_TOKEN_STORAGE")
        self.api_token_verifier = os.getenv("API_TOKEN_VERIFIER")
        self.api_token_publisher = os.getenv("API_TOKEN_PUBLISHER")

        # ---------------------------------------------------------
        # Services
        # ---------------------------------------------------------

        self.reader_url_list: list[str] = []
        self.verifier_url_list: list[str] = []
        self.storage_url_list: list[str] = []
        self.publisher_url_list: list[str] = []

        # ---------------------------------------------------------
        # Stream configuration
        # ---------------------------------------------------------

        self.stream = False

        # Servicios de los que este Manager puede consumir streams
        self.stream_readers = True
        self.stream_verifiers = False
        self.stream_storages = False
        self.stream_publishers = False

        # ---------------------------------------------------------
        # Dynamic registration
        #
        # Permite que servicios externos soliciten registrarse
        # dinámicamente en este Manager.
        # ---------------------------------------------------------

        self.add_readers = False
        self.add_verifiers = False
        self.add_storages = False
        self.add_publishers = False

        # ---------------------------------------------------------
        # Load JSON configuration
        # ---------------------------------------------------------

        self._load_json(Path(config_path))

    def _load_json(self, path: Path) -> None:

        if not path.exists():
            raise FileNotFoundError(
                f"Manager configuration file not found: {path}"
            )

        with path.open("r", encoding="utf-8") as file:
            config = json.load(file)

        # Services

        services = config.get("services", {})

        self.reader_url_list = services.get("readers", [])
        self.verifier_url_list = services.get("verifiers", [])
        self.storage_url_list = services.get("storages", [])
        self.publisher_url_list = services.get("publishers", [])

        # Stream

        stream = config.get("stream", {})

        self.stream = stream.get("enabled", False)

        self.stream_readers = stream.get("readers", True)
        self.stream_verifiers = stream.get("verifiers", False)
        self.stream_storages = stream.get("storages", False)
        self.stream_publishers = stream.get("publishers", False)

        # Dynamic registration

        registration = config.get("allowRegistration", {})

        self.add_readers = registration.get("readers", False)
        self.add_verifiers = registration.get("verifiers", False)
        self.add_storages = registration.get("storages", False)
        self.add_publishers = registration.get("publishers", False)