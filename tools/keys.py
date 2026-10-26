"""Claves de Phonendo en un único sitio: keys/ (fuera de git).

- keys/verifiers/<nombre>.json: clave ed25519 con la que firma un Verifier (JWK).
  Su clave pública en hex es el verifierId y la que guarda el contrato.
- keys/stellar/identity/<alias>.toml: carteras Stellar del Publisher, en el formato
  de la Stellar CLI (sirve con `stellar --config-dir keys/stellar ...`).
El Verifier no tiene cartera: solo firma. La cartera del Publisher solo paga comisiones.
"""
import argparse
import base64
import csv
import getpass
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS = ROOT / 'keys'
VERIFIERS = KEYS / 'verifiers'
STELLAR = KEYS / 'stellar'
WALLETS = STELLAR / 'identity'
DEFAULT_VERIFIER = 'dev'
DEFAULT_WALLET = 'phonendo'
# Claves anteriores: la de desarrollo que conocen los contratos de testnet y la cartera de la CLI.
LEGACY_VERIFIER = (ROOT / 'circuits/build/verifier_dev_key.json', ROOT / 'apps/verifier/signing_key.json')
CLI_WALLETS = Path.home() / '.config/stellar/identity'
FRIENDBOT = 'https://friendbot.stellar.org/?addr='
NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,62}')


def crc16_xmodem(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


def strkey(version, payload):
    data = bytes([version]) + payload
    return base64.b32encode(data + crc16_xmodem(data).to_bytes(2, 'little')).decode()


def strkey_payload(version, value):
    raw = base64.b32decode(value)
    if len(raw) != 35 or raw[0] != version or crc16_xmodem(raw[:33]) != int.from_bytes(raw[33:], 'little'):
        raise ValueError('Clave Stellar no válida')
    return raw[1:33]


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def check_name(value):
    if not NAME.fullmatch(value):
        raise ValueError(f'Nombre no válido: {value!r} (minúsculas, números, - y _)')
    return value


def private_file(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    path.chmod(0o600)


def verifier_path(name):
    return VERIFIERS / f'{check_name(name)}.json'


def wallet_path(alias):
    return WALLETS / f'{check_name(alias)}.toml'


def verifier_id(path):
    """Clave pública en hex (verifierId) de una clave de Verifier."""
    jwk = json.loads(Path(path).read_text(encoding='utf-8'))
    if 'x' in jwk:
        return unb64(jwk['x']).hex()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(unb64(jwk['d'])).public_key().public_bytes_raw().hex()


def wallet_address(alias):
    """Dirección G de una cartera, o None si no se puede calcular aquí."""
    text = wallet_path(alias).read_text(encoding='utf-8')
    secret = re.search(r'secret_key\s*=\s*"(S[A-Z2-7]{55})"', text)
    if secret:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        seed = strkey_payload(18 << 3, secret.group(1))
        return strkey(6 << 3, Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw())
    # Frase semilla (cartera importada de la CLI): la dirección la deriva la propia CLI.
    if shutil.which('stellar'):
        result = subprocess.run(['stellar', '--config-dir', str(STELLAR), 'keys', 'address', alias],
                                capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    return None


def inventory():
    """Claves disponibles, solo con su parte pública."""
    verifiers = [{'name': path.stem, 'verifierId': verifier_id(path)} for path in sorted(VERIFIERS.glob('*.json'))]
    wallets = [{'alias': path.stem, 'address': wallet_address(path.stem)} for path in sorted(WALLETS.glob('*.toml'))]
    return {'verifiers': verifiers, 'wallets': wallets}


def new_verifier(name, force=False):
    path = verifier_path(name)
    if path.exists() and not force:
        raise ValueError(f'Ya existe {path.relative_to(ROOT)}; usa --force para sustituirla')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    private_file(path, json.dumps({'kty': 'OKP', 'crv': 'Ed25519', 'd': b64(key.private_bytes_raw()),
                                   'x': b64(key.public_key().public_bytes_raw())}))
    return path


def fund(address):
    try:
        with urllib.request.urlopen(FRIENDBOT + address, timeout=30) as response:
            return response.status == 200
    except OSError as error:
        # Friendbot responde 400 si la cuenta ya existe: ya tiene fondos.
        return getattr(error, 'code', None) == 400


def new_wallet(alias, force=False, funded=True):
    path = wallet_path(alias)
    if path.exists():
        if not force:
            raise ValueError(f'Ya existe {path.relative_to(ROOT)}; usa --force para sustituirla')
        # La cartera anterior puede ser admin de contratos: se guarda copia, no se pierde.
        shutil.copyfile(path, path.with_name(f'{alias}.toml.{int(time.time())}.bak'))
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    private_file(path, f'secret_key = "{strkey(18 << 3, key.private_bytes_raw())}"\n')
    address = strkey(6 << 3, key.public_key().public_bytes_raw())
    if funded and not fund(address):
        print(f'Aviso: no se pudo fondear {address} con Friendbot; fondea la cuenta en testnet.', file=sys.stderr)
    return path, address


def add_wallet(alias, secret, force=False):
    path = wallet_path(alias)
    if path.exists() and not force:
        raise ValueError(f'Ya existe {path.relative_to(ROOT)}; usa --force para sustituirla')
    strkey_payload(18 << 3, secret)
    private_file(path, f'secret_key = "{secret}"\n')
    return path


def init(regenerate_wallets=False):
    """Deja keys/ lista sin tocar lo que ya exista. Devuelve los mensajes para el usuario."""
    notes = []
    target = verifier_path(DEFAULT_VERIFIER)
    if not target.exists():
        legacy = next((path for path in LEGACY_VERIFIER if path.is_file()), None)
        if legacy:
            private_file(target, legacy.read_text(encoding='utf-8'))
            notes.append(f'Clave del Verifier copiada de {legacy.relative_to(ROOT)} a {target.relative_to(ROOT)}')
        else:
            new_verifier(DEFAULT_VERIFIER)
            notes.append(f'Clave nueva del Verifier ({verifier_id(target)}): despliega un contrato con ella')
    wallets = sorted(WALLETS.glob('*.toml'))
    if regenerate_wallets:
        for path in wallets or [wallet_path(DEFAULT_WALLET)]:
            _, address = new_wallet(path.stem, force=path.exists())
            notes.append(f'Cartera {path.stem} regenerada: {address}')
    elif not wallet_path(DEFAULT_WALLET).exists():
        legacy = CLI_WALLETS / f'{DEFAULT_WALLET}.toml'
        if legacy.is_file():
            private_file(wallet_path(DEFAULT_WALLET), legacy.read_text(encoding='utf-8'))
            notes.append(f'Cartera {DEFAULT_WALLET} copiada de la Stellar CLI')
        else:
            _, address = new_wallet(DEFAULT_WALLET)
            notes.append(f'Cartera {DEFAULT_WALLET} creada y fondeada en testnet: {address}')
    return notes


def contract_verifier_key(contract, network='testnet'):
    """verifierId (hex) que un contrato `adherence` tiene guardado, leído de la red."""
    result = subprocess.run(['stellar', 'contract', 'read', '--id', contract, '--network', network,
                             '--config-dir', str(STELLAR), '--output', 'json'], capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f'No se pudo leer {contract}: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "error de la CLI"}')
    instance = json.loads(next(csv.reader(io.StringIO(result.stdout)))[1])['contract_instance']['storage']
    for entry in instance:
        for field in entry['val'].get('map', []):
            if field['key'].get('symbol') == 'verifier_key':
                return field['val']['bytes']
    raise ValueError(f'{contract} no parece un contrato adherence (sin verifier_key)')


def check_contract(contract, network='testnet'):
    """Qué claves de keys/verifiers puede cobrar en ese contrato. Devuelve (clave del contrato, nombres)."""
    trusted = contract_verifier_key(contract, network)
    return trusted, [item['name'] for item in inventory()['verifiers'] if item['verifierId'] == trusted]


def deploy_hint(name):
    return ('stellar contract deploy --config-dir keys/stellar --wasm contracts/target/wasm32v1-none/release/adherence.wasm '
            f'--source {DEFAULT_WALLET} --network testnet -- --admin {DEFAULT_WALLET} --verifier_key {verifier_id(verifier_path(name))} '
            '--token <id USDC> --policy-file-path contracts/policy.json '
            '--verification_key-file-path circuits/build/soroban_vk.json')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='tools/keys.sh', description='Claves de Verifiers y carteras de Publishers en keys/')
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('init', help='crea lo que falte (clave dev del Verifier y cartera phonendo)')
    start.add_argument('--regenerate-wallets', action='store_true', help='sustituye las carteras por otras nuevas (guarda copia)')
    commands.add_parser('ls', help='lista claves y carteras (solo la parte pública)')
    verifier = commands.add_parser('verifier', help='claves de firma de los Verifiers').add_subparsers(dest='action', required=True)
    item = verifier.add_parser('new')
    item.add_argument('name')
    item.add_argument('--force', action='store_true')
    verifier.add_parser('show').add_argument('name')
    item = verifier.add_parser('check', help='comprueba si alguna clave tuya es la que confía un contrato')
    item.add_argument('contract')
    item.add_argument('--network', default='testnet')
    wallet = commands.add_parser('wallet', help='carteras Stellar de los Publishers').add_subparsers(dest='action', required=True)
    item = wallet.add_parser('new')
    item.add_argument('alias')
    item.add_argument('--force', action='store_true')
    item.add_argument('--no-fund', action='store_true')
    item = wallet.add_parser('add', help='guarda una clave secreta S... existente (se pide sin eco)')
    item.add_argument('alias')
    item.add_argument('--force', action='store_true')
    wallet.add_parser('show').add_argument('alias')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            for note in init(args.regenerate_wallets):
                print(note)
            print('Claves listas en keys/')
        elif args.command == 'ls':
            keys = inventory()
            print('Verifiers (keys/verifiers):')
            for item in keys['verifiers']:
                print(f"  {item['name']:<20} {item['verifierId']}")
            print('Carteras (keys/stellar/identity):')
            for item in keys['wallets']:
                print(f"  {item['alias']:<20} {item['address'] or '(instala la Stellar CLI para ver la dirección)'}")
        elif args.command == 'verifier' and args.action == 'new':
            path = new_verifier(args.name, args.force)
            print(f'verifierId: {verifier_id(path)}')
            print('Despliega su contrato con:\n  ' + deploy_hint(args.name))
        elif args.command == 'verifier' and args.action == 'check':
            trusted, names = check_contract(args.contract, args.network)
            print(f'El contrato confía en: {trusted}')
            if names:
                print(f"OK: lo firma keys/verifiers/{names[0]}.json (VERIFIER_KEY={names[0]})")
            else:
                print('Ninguna clave de keys/verifiers coincide: sus sesiones no se podrán cobrar.\n'
                      'Pide a quien lo desplegó su clave (keys/verifiers/<nombre>.json) o despliega otro contrato '
                      'con ./tools/keys.sh verifier new <nombre>.')
                return 2
        elif args.command == 'verifier':
            print(verifier_id(verifier_path(args.name)))
        elif args.command == 'wallet' and args.action == 'new':
            _, address = new_wallet(args.alias, args.force, not args.no_fund)
            print(address)
        elif args.command == 'wallet' and args.action == 'add':
            add_wallet(args.alias, getpass.getpass('Clave secreta S...: ').strip(), args.force)
            print(wallet_address(args.alias))
        else:
            if not wallet_path(args.alias).exists():
                raise ValueError(f'No existe la cartera {args.alias}')
            print(wallet_address(args.alias))
    except (ValueError, FileNotFoundError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
