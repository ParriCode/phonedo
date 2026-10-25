"""Firma ed25519 del lote que comprueba el contrato.

Mensaje: commitment (32 B) || sessionId (32 B big-endian) || clave de la cuenta G
de la paciente (32 B). Igual que circuits/scripts/sign.js. De momento usa la
clave de desarrollo; quién firma en producción está pendiente de decidir.
"""
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


def crc16_xmodem(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


def account_key(address):
    """Clave pública ed25519 (32 B) de una dirección G."""
    try:
        raw = base64.b32decode(address)
    except (ValueError, TypeError):
        raise ValueError('Cuenta G no válida')
    if len(raw) != 35 or raw[0] != 6 << 3 or crc16_xmodem(raw[:33]) != int.from_bytes(raw[33:], 'little'):
        raise ValueError('Cuenta G no válida')
    return raw[1:33]


def batch_message(commitment_hex, session_id, patient):
    return bytes.fromhex(commitment_hex) + int(session_id).to_bytes(32, 'big') + account_key(patient)


def _b64url(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


class LocalSigner:
    """Firma con la clave de desarrollo que genera circuits/scripts/sign.js."""

    def __init__(self, key_path):
        jwk = json.loads(Path(key_path).read_text(encoding='utf-8'))
        self.private_key = Ed25519PrivateKey.from_private_bytes(_b64url(jwk['d']))

    def public_key_hex(self):
        return self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def sign(self, batch, commitment_hex, patient):
        return self.private_key.sign(batch_message(commitment_hex, batch['sessionId'], patient)).hex()
