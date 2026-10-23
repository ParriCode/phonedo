"""Canonical HMAC authentication of Captured event envelopes."""
import os
import json
import hmac
import hashlib

def sign_event(message: dict) -> str:
    secret = os.getenv('MANAGER_PASSWORD')
    if not secret:
        raise RuntimeError('MANAGER_PASSWORD is not configured')
    value = dict(message['value'])
    value.pop('managerHash', None)
    envelope = {**message, 'value': value}
    encoded = json.dumps(envelope, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hmac.new(secret.encode('utf-8'), encoded, hashlib.sha256).hexdigest()

