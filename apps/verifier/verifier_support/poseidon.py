"""Compromiso Poseidon del lote, idéntico a circuits/lib/commitment.circom.

Reproduce el Poseidon optimizado de circomlib para 4 entradas (t = 5) sobre el
campo de BLS12-381. Las constantes de poseidon_t5.json salen de
circomlib/circuits/poseidon_constants.circom.
"""
import json
from pathlib import Path

FIELD = 0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001
T = 5
FULL_ROUNDS = 8
PARTIAL_ROUNDS = 60
PER_WORD = 30
BATCH_SIZE = 32

_constants = json.loads((Path(__file__).with_name('poseidon_t5.json')).read_text(encoding='utf-8'))
C = [int(value, 16) for value in _constants['C']]
S = [int(value, 16) for value in _constants['S']]
M = [[int(_constants['M'][i * T + j], 16) for j in range(T)] for i in range(T)]
P = [[int(_constants['P'][i * T + j], 16) for j in range(T)] for i in range(T)]


def _sigma(value):
    return pow(value, 5, FIELD)


def _mix(state, matrix):
    return [sum(matrix[j][i] * state[j] for j in range(T)) % FIELD for i in range(T)]


def poseidon(inputs):
    if len(inputs) != T - 1:
        raise ValueError('Poseidon espera 4 entradas')
    state = [(value + C[i]) % FIELD for i, value in enumerate([0] + [int(v) % FIELD for v in inputs])]
    half = FULL_ROUNDS // 2
    for r in range(half - 1):
        state = [(_sigma(value) + C[(r + 1) * T + i]) % FIELD for i, value in enumerate(state)]
        state = _mix(state, M)
    state = [(_sigma(value) + C[half * T + i]) % FIELD for i, value in enumerate(state)]
    state = _mix(state, P)
    for r in range(PARTIAL_ROUNDS):
        state[0] = (_sigma(state[0]) + C[(half + 1) * T + r]) % FIELD
        base = (2 * T - 1) * r
        first = sum(S[base + i] * state[i] for i in range(T)) % FIELD
        state = [first] + [(state[i] + state[0] * S[base + T + i - 1]) % FIELD for i in range(1, T)]
    for r in range(half - 1):
        offset = (half + 1) * T + PARTIAL_ROUNDS + r * T
        state = [(_sigma(value) + C[offset + i]) % FIELD for i, value in enumerate(state)]
        state = _mix(state, M)
    state = [_sigma(value) for value in state]
    return sum(M[j][0] * state[j] for j in range(T)) % FIELD


def batch_commitment(readings, salt, session_id):
    """Poseidon(sessionId, salt, lecturas empaquetadas de 30 en 30), como el circuito."""
    if len(readings) != BATCH_SIZE or any(not 0 <= r <= 255 for r in readings):
        raise ValueError('El lote debe tener 32 lecturas de 0 a 255')
    words = [sum(r * 256 ** j for j, r in enumerate(readings[w:w + PER_WORD]))
             for w in range(0, len(readings), PER_WORD)]
    return poseidon([int(session_id), int(salt)] + words)
