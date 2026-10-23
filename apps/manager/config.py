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

        self.verifier_url_list: list[str] = []
        self.storage_url_list: list[str] = []
        self.publisher_url_list: list[str] = []

        # ---------------------------------------------------------
        # Independent publication and subscription settings are loaded from JSON.

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

        self.port = int(os.getenv('PORT_MANAGER', config.get('server', {}).get('port', self.port)))
        self.host = config.get('server', {}).get('host', '0.0.0.0')
        self.http_timeout = float(os.getenv('MANAGER_HTTP_TIMEOUT_SECONDS', config.get('httpTimeoutSeconds', 10)))
        self.queue_size = int(os.getenv('MANAGER_QUEUE_SIZE', config.get('queue', {}).get('size', 1000)))
        self.retry_interval = float(os.getenv('MANAGER_RETRY_INTERVAL_SECONDS', config.get('queue', {}).get('retryIntervalSeconds', 5)))
        if self.http_timeout <= 0 or self.queue_size <= 0 or self.retry_interval <= 0:
            raise ValueError('Timeout and queue settings must be positive')
        # Services

        services = config.get("services", {})

        self.verifier_url_list = services.get("verifiers", [])
        self.storage_url_list = services.get("storages", [])
        self.publisher_url_list = services.get("publishers", [])
        self.stream_enabled = config.get('stream', {}).get('enabled', False)
        outputs = config.get('outputStreams', {})
        self.output_verifiers = outputs.get('verifiers', False)
        self.output_storages = outputs.get('storages', False)
        subscriptions = config.get('subscriptions', {})
        self.reader_subscriptions = subscriptions.get('readers', [])
        self.verifier_subscriptions = subscriptions.get('verifiers', [])
        self.storage_subscriptions = subscriptions.get('storages', [])
        for targets in (self.reader_subscriptions, self.verifier_subscriptions, self.storage_subscriptions):
            if not isinstance(targets, list):
                raise ValueError('Las suscripciones deben ser listas de URLs o destinos')

        # Dynamic registration

        registration = config.get("allowRegistration", {})

        self.add_readers = registration.get("readers", False)
        self.add_verifiers = registration.get("verifiers", False)
        self.add_storages = registration.get("storages", False)
        self.add_publishers = registration.get("publishers", False)