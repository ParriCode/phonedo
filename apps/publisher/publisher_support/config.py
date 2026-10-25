"""Configuración del Publisher: Managers, política, pacientes, firma y contrato."""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


class PublisherConfig:
    def __init__(self, path=None):
        path = Path(path or os.getenv('PUBLISHER_CONFIG_PATH', str(BASE_DIR / 'config.json')))
        data = json.loads(path.read_text(encoding='utf-8'))
        server = data.get('server', {})
        self.host = server.get('host', '0.0.0.0')
        self.port = int(os.getenv('PORT_PUBLISHER', server.get('port', 5000)))
        self.manager_subscriptions = data.get('subscriptions', {}).get('managers', [])
        self.batch_size = int(data.get('batchSize', 32))
        policy = data.get('policy', {})
        self.policy = {
            'minValue': int(policy.get('minValue', 90)),
            'maxValue': int(policy.get('maxValue', 130)),
            'minCount': int(policy.get('minCount', 28)),
        }
        self.patients = data.get('patients', {})
        managers = [m if isinstance(m, str) else m.get('url', '') for m in self.manager_subscriptions]
        self.signer_manager = data.get('signer', {}).get('manager') or (managers[0] if managers else '')
        self.circuits_path = (BASE_DIR / data.get('circuitsPath', '../../circuits')).resolve()
        self.stellar = dict(data.get('stellar', {}))
        if os.getenv('PUBLISHER_STELLAR_SOURCE'):
            self.stellar['source'] = os.environ['PUBLISHER_STELLAR_SOURCE']

    def patient_for(self, device_id):
        return self.patients.get(device_id) or self.patients.get('default')
