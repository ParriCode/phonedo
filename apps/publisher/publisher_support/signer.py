"""Firma ed25519 del lote que comprueba el contrato.

La firma la da el Verifier, que es quien comprobó las lecturas. El Publisher se la
pide a POST /signBatch del Manager y no firma nada por su cuenta.
"""
import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


def account_key(address):
    import base64
    raw = base64.b32decode(address)
    if len(raw) != 35 or raw[0] != 48:
        raise ValueError('Cuenta patient inválida')
    return raw[1:33]


class ManagerSigner:
    """Pide la firma a POST /signBatch del Manager, que la reenvía al Verifier."""

    def __init__(self, manager_url, token, timeout=10):
        self.url = manager_url.rstrip('/') + '/signBatch'
        self.token = token
        self.timeout = timeout

    def sign(self, batch, commitment_hex, patient):
        response = requests.post(self.url, timeout=self.timeout, json={
            'token': self.token, 'sessionId': batch['sessionId'], 'salt': batch['salt'],
            'patient': patient, 'eventKeys': batch['eventKeys'],
            **{field: batch[field] for field in ('managerId', 'verifierId', 'readerId')}})
        if not response.ok:
            raise RuntimeError(f'signBatch devolvió {response.status_code}: {response.text}')
        reply = response.json()
        # El Verifier calcula el commitment con sus propias lecturas: debe coincidir con la prueba
        if reply.get('commitment') != commitment_hex:
            raise ValueError('El commitment firmado no coincide con el de la prueba')
        if reply.get('verifierId') != batch['verifierId']:
            raise ValueError('La firma pertenece a otro Verifier')
        public_key = bytes.fromhex(batch['verifierId'])
        message = bytes.fromhex(commitment_hex) + batch['sessionId'].to_bytes(32, 'big') + account_key(patient) + public_key
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(bytes.fromhex(reply['signature']), message)
        except InvalidSignature as error:
            raise ValueError('La firma del lote no es válida para este Verifier') from error
        return reply['signature']
