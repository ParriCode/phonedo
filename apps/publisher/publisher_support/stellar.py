"""Llama a claim() del contrato con la CLI de Stellar y su alias de cuenta."""
import re
import subprocess

TX_HASH = re.compile(r'/tx/([0-9a-f]{64})')
ALREADY_CLAIMED = 'Error(Contract, #1)'
INVALID_PROOF = 'Error(Contract, #2)'


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
            if INVALID_PROOF in output:
                raise ClaimFailed('La prueba no coincide con la política o la clave de verificación del contrato')
            if re.search(r'insufficient|underfunded|low balance|saldo insuficiente', output, re.I):
                raise ClaimFailed('Saldo insuficiente en la cuenta emisora o en el contrato para pagar la sesión')
            if re.search(r'ed25519|invalid signature|signature verification', output, re.I):
                raise ClaimFailed('Firma del Verifier rechazada por el contrato: comprueba su clave pública')
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            raise ClaimFailed(' | '.join(lines[-8:])[:1000] if lines else 'claim falló sin detalle en la CLI')
        match = TX_HASH.search(output)
        return match.group(1) if match else None
