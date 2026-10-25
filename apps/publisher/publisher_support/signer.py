"""Firma ed25519 del lote que comprueba el contrato.

La firma la da el Verifier, que es quien comprobó las lecturas. El Publisher se la
pide a POST /signBatch del Manager y no firma nada por su cuenta.
"""
import requests


class ManagerSigner:
    """Pide la firma a POST /signBatch del Manager, que la reenvía al Verifier."""

    def __init__(self, manager_url, token, timeout=10):
        self.url = manager_url.rstrip('/') + '/signBatch'
        self.token = token
        self.timeout = timeout

    def sign(self, batch, commitment_hex, patient):
        response = requests.post(self.url, timeout=self.timeout, json={
            'token': self.token, 'sessionId': batch['sessionId'], 'salt': batch['salt'],
            'patient': patient, 'eventKeys': batch['eventKeys']})
        if not response.ok:
            raise RuntimeError(f'signBatch devolvió {response.status_code}: {response.text}')
        reply = response.json()
        # El Verifier calcula el commitment con sus propias lecturas: debe coincidir con la prueba
        if reply.get('commitment') != commitment_hex:
            raise ValueError('El commitment firmado no coincide con el de la prueba')
        return reply['signature']
