"""Agrupa lecturas Verified por Manager, Verifier, Reader y dispositivo."""
import threading


def reading_from_event(message):
    """Lectura entera de 0 a 255 de un evento Verified, o None si no sirve."""
    if not isinstance(message, dict) or not isinstance(message.get('value'), dict):
        return None
    value = message['value']
    if value.get('status') != 'Verified' or not value.get('verifierSign'):
        return None
    payload = value.get('payload')
    result = payload.get('simple_result') if isinstance(payload, dict) else None
    if isinstance(result, bool) or not isinstance(result, (int, float)):
        return None
    return min(255, max(0, round(result)))


class SessionBatcher:
    def __init__(self, size, remembered=4096):
        self.size = size
        self.pending = {}
        self.seen = {}
        self.remembered = remembered
        self.lock = threading.Lock()

    def add(self, message, manager_url=None, manager_token=None):
        """Añade el evento y devuelve el lote cuando el dispositivo llega a `size`."""
        reading = reading_from_event(message)
        if reading is None:
            return None
        value = message['value']
        device_id = value.get('deviceId')
        fields = ('managerId', 'verifierId', 'readerId', 'observationId', 'deviceId')
        if any(not isinstance(value.get(field), str) or not value[field] for field in fields):
            return None
        if not isinstance(message.get('key'), str) or not message['key']:
            return None
        identity = tuple(value[field] for field in fields[:4])
        origin = tuple(value[field] for field in ('managerId', 'verifierId', 'readerId', 'deviceId'))
        with self.lock:
            # El stream no garantiza entregas únicas: cada evento cuenta una vez.
            if identity in self.seen:
                return None
            self.seen[identity] = True
            if len(self.seen) > self.remembered:
                self.seen.pop(next(iter(self.seen)))
            batch = self.pending.setdefault(origin, {**{field: value[field] for field in fields if field != 'observationId'},
                                                        'managerUrl': manager_url, 'managerToken': manager_token,
                                                        'deviceId': device_id, 'readings': [], 'eventKeys': [],
                                                        'startedAt': int(value.get('creationDatetime', 0))})
            batch['readings'].append(reading)
            batch['eventKeys'].append(message.get('key'))
            if len(batch['readings']) < self.size:
                return None
            return self.pending.pop(origin)
