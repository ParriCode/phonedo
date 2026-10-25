"""Llama a claim() del contrato con la CLI de Stellar y su alias de cuenta."""
import re
import subprocess

TX_HASH = re.compile(r'/tx/([0-9a-f]{64})')
ALREADY_CLAIMED = 'Error(Contract, #1)'


class ClaimFailed(Exception):
    pass


class StellarClaimer:
    def __init__(self, contract_id, source, network='testnet', timeout=120):
        self.contract_id = contract_id
        self.source = source
        self.network = network
        self.timeout = timeout

    def command(self, batch, patient, commitment_hex, signature_hex, proof_file):
        return ['stellar', 'contract', 'invoke', '--id', self.contract_id, '--source', self.source,
                '--network', self.network, '--', 'claim', '--patient', patient,
                '--session_id', str(batch['sessionId']), '--commitment', commitment_hex,
                '--signature', signature_hex, '--proof-file-path', str(proof_file)]

    def claim(self, batch, patient, commitment_hex, signature_hex, proof_file):
        """Envía el claim y devuelve el hash de la transacción."""
        result = subprocess.run(self.command(batch, patient, commitment_hex, signature_hex, proof_file),
                                capture_output=True, text=True, encoding='utf-8', errors='replace',
                                timeout=self.timeout)
        output = result.stdout + result.stderr
        if result.returncode != 0:
            if ALREADY_CLAIMED in output:
                raise ClaimFailed('Sesión ya cobrada')
            lines = [line for line in output.splitlines() if 'error' in line.lower()]
            raise ClaimFailed(lines[0].strip() if lines else 'claim falló')
        match = TX_HASH.search(output)
        return match.group(1) if match else None
