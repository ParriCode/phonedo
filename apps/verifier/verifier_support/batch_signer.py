"""Clave ed25519 del Verifier y firma de lotes de 32 lecturas para el contrato `adherence`.

El Verifier recuerda las lecturas de los eventos que ha verificado. Al firmar un
lote solo usa esas lecturas, nunca las que envía quien pide la firma.
Mensaje firmado: commitment (32 B) || sessionId (32 B big-endian) || clave de
la cuenta G de la paciente (32 B) || verifierId (32 B), igual que sign.js.
"""
import base64
import json
import threading
from collections import OrderedDict
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from verifier_support.poseidon import BATCH_SIZE, FIELD, batch_commitment


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
        raise ValueError('patient must be a valid G account')
    if len(raw) != 35 or raw[0] != 6 << 3 or crc16_xmodem(raw[:33]) != int.from_bytes(raw[33:], 'little'):
        raise ValueError('patient must be a valid G account')
    return raw[1:33]


def reading_from_payload(payload):
    """Lectura entera de 0 a 255 (`simple_result` redondeado), o None."""
    result = payload.get('simple_result') if isinstance(payload, dict) else None
    if isinstance(result, bool) or not isinstance(result, (int, float)):
        return None
    return min(255, max(0, round(result)))


def load_signing_key(path):
    """Clave JWK ed25519 (formato de sign.js) o None si el archivo no existe."""
    path = Path(path)
    if not path.is_file():
        return None
    jwk = json.loads(path.read_text(encoding='utf-8'))
    seed = base64.urlsafe_b64decode(jwk['d'] + '=' * (-len(jwk['d']) % 4))
    return Ed25519PrivateKey.from_private_bytes(seed)


class BatchSigner:
    def __init__(self, private_key, remembered=4096):
        self.private_key = private_key
        self.verifier_id = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        self.remembered = remembered
        self.readings = OrderedDict()
        self.lock = threading.Lock()

    def remember(self, message):
        """Guarda la lectura de un evento recién verificado."""
        value = message['value']
        reading = reading_from_payload(value.get('payload'))
        if reading is None:
            return
        with self.lock:
            self.readings[message['key']] = (value.get('managerId'), value.get('readerId'), value.get('deviceId'), reading)
            while len(self.readings) > self.remembered:
                self.readings.popitem(last=False)

    def sign(self, session_id, salt, patient, event_keys, manager_id=None, reader_id=None):
        """Devuelve (commitment hex, firma hex) o lanza ValueError."""
        if isinstance(session_id, bool) or not isinstance(session_id, int) or not 0 < session_id < 2 ** 64:
            raise ValueError('sessionId must be a positive 64-bit integer')
        try:
            salt = int(salt)
        except (TypeError, ValueError):
            raise ValueError('salt must be an integer')
        if not 0 <= salt < FIELD:
            raise ValueError('salt is out of range')
        patient_key = account_key(patient)
        if not isinstance(event_keys, list) or len(event_keys) != BATCH_SIZE or len(set(map(str, event_keys))) != BATCH_SIZE:
            raise ValueError(f'eventKeys must list {BATCH_SIZE} different events')
        with self.lock:
            known = [self.readings.get(key) for key in event_keys]
        if None in known:
            raise ValueError('eventKeys contains events not verified by this Verifier')
        if len({item[:3] for item in known}) != 1:
            raise ValueError('eventKeys deben pertenecer al mismo Manager, Reader y dispositivo')
        if known[0][:2] != (manager_id, reader_id):
            raise ValueError('El origen del lote no coincide con los eventos verificados')
        commitment = batch_commitment([item[3] for item in known], salt, session_id).to_bytes(32, 'big')
        message = commitment + session_id.to_bytes(32, 'big') + patient_key + bytes.fromhex(self.verifier_id)
        return commitment.hex(), self.private_key.sign(message).hex()
