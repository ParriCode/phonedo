"""Storage instance configuration and Manager subscriptions."""
import json
import os
from pathlib import Path


class StorageConfig:
    def __init__(self, path=None):
        path = Path(path or os.getenv('STORAGE_CONFIG_PATH', str(Path(__file__).resolve().parents[1] / 'config.json')))
        data = json.loads(path.read_text(encoding='utf-8'))
        self.host = data.get('server', {}).get('host', '0.0.0.0')
        self.port = int(os.getenv('PORT_STORAGE', data.get('server', {}).get('port', 5000)))
        self.database_path = os.getenv('PHONENDO_DB_PATH', data.get('databasePath', '/tmp/phonendo_db_path'))
        self.manager_subscriptions = data.get('subscriptions', {}).get('managers', [])
        self.stream_enabled = data.get('stream', {}).get('enabled', True)
        self.token = os.getenv('API_TOKEN_STORAGE', data.get('token', ''))
