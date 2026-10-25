"""Agrupa lecturas Verified de cada dispositivo en lotes de tamaño fijo."""
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

    def add(self, message):
        """Añade el evento y devuelve el lote cuando el dispositivo llega a `size`."""
        reading = reading_from_event(message)
        if reading is None:
            return None
        value = message['value']
        device_id = value.get('deviceId')
        with self.lock:
            # El stream no garantiza entregas únicas: cada evento cuenta una vez.
            if message.get('key') in self.seen:
                return None
            self.seen[message.get('key')] = True
            if len(self.seen) > self.remembered:
                self.seen.pop(next(iter(self.seen)))
            batch = self.pending.setdefault(device_id, {'deviceId': device_id, 'readings': [],
                                                        'startedAt': int(value.get('creationDatetime', 0))})
            batch['readings'].append(reading)
            if len(batch['readings']) < self.size:
                return None
            return self.pending.pop(device_id)
