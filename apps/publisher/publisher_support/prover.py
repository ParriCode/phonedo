"""Genera la prueba Groth16 de un lote con los scripts de circuits/."""
import json
import os
import subprocess
import tempfile
from pathlib import Path


class BatchNotMet(Exception):
    """El lote no cumple la política: no existe prueba."""


class Prover:
    def __init__(self, circuits_path, policy, timeout=300):
        self.circuits_path = Path(circuits_path)
        self.build = self.circuits_path / 'build'
        self.policy = policy
        self.timeout = timeout

    def _node(self, *args, out):
        # Cada lote escribe en su carpeta (PROOF_DIR): varios Publishers comparten build/ sin pisarse.
        return subprocess.run(['node', *args], cwd=self.circuits_path, capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=self.timeout,
                              env={**os.environ, 'PROOF_DIR': str(out)})

    def prove(self, batch, policy=None):
        """Devuelve el compromiso (hex) y la ruta de la prueba para el contrato."""
        inputs = {'readings': batch['readings'], 'salt': batch['salt'],
                  'sessionId': str(batch['sessionId']), **(policy or self.policy)}
        (self.build / 'publisher').mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix=f"session_{batch['sessionId']}_", dir=self.build / 'publisher'))
        input_file = out / 'publisher_input.json'
        input_file.write_text(json.dumps(inputs), encoding='utf-8')
        proved = self._node('scripts/prove.js', str(input_file), out=out)
        if proved.returncode != 0:
            if 'no cumple' in proved.stderr:
                raise BatchNotMet(proved.stderr.strip().splitlines()[-1])
            raise RuntimeError(proved.stderr.strip() or 'prove.js falló')
        exported = self._node('scripts/soroban.js', out=out)
        if exported.returncode != 0:
            raise RuntimeError(exported.stderr.strip() or 'soroban.js falló')
        args = json.loads((out / 'soroban_args.json').read_text(encoding='utf-8'))
        proof_file = out / f"proof_{batch['sessionId']}.json"
        proof_file.write_text(json.dumps(args['proof']), encoding='utf-8')
        if args['session_id'] != str(batch['sessionId']):
            raise RuntimeError('La prueba no corresponde a la sesión')
        return args['commitment'], proof_file
