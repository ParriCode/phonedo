"""Genera la prueba Groth16 de un lote con los scripts de circuits/."""
import json
import subprocess
import threading
from pathlib import Path


class BatchNotMet(Exception):
    """El lote no cumple la política: no existe prueba."""


class Prover:
    def __init__(self, circuits_path, policy, timeout=300):
        self.circuits_path = Path(circuits_path)
        self.build = self.circuits_path / 'build'
        self.policy = policy
        self.timeout = timeout
        # prove.js y soroban.js escriben en build/: un lote cada vez.
        self.lock = threading.Lock()

    def _node(self, *args):
        return subprocess.run(['node', *args], cwd=self.circuits_path, capture_output=True,
                              text=True, timeout=self.timeout)

    def prove(self, batch):
        """Devuelve el compromiso (hex) y la ruta de la prueba para el contrato."""
        inputs = {'readings': batch['readings'], 'salt': batch['salt'],
                  'sessionId': str(batch['sessionId']), **self.policy}
        with self.lock:
            input_file = self.build / 'publisher_input.json'
            input_file.write_text(json.dumps(inputs), encoding='utf-8')
            proved = self._node('scripts/prove.js', str(input_file))
            if proved.returncode != 0:
                if 'no cumple' in proved.stderr:
                    raise BatchNotMet(proved.stderr.strip().splitlines()[-1])
                raise RuntimeError(proved.stderr.strip() or 'prove.js falló')
            exported = self._node('scripts/soroban.js')
            if exported.returncode != 0:
                raise RuntimeError(exported.stderr.strip() or 'soroban.js falló')
            args = json.loads((self.build / 'soroban_args.json').read_text(encoding='utf-8'))
            proof_file = self.build / f"proof_{batch['sessionId']}.json"
            proof_file.write_text(json.dumps(args['proof']), encoding='utf-8')
        if args['session_id'] != str(batch['sessionId']):
            raise RuntimeError('La prueba no corresponde a la sesión')
        return args['commitment'], proof_file
