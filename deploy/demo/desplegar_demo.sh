#!/usr/bin/env bash
# SOLO TESTNET / CLAVES DE DEMOSTRACIÓN.
# Deja la demo lista para cobrar en Stellar testnet: fondea la cuenta `phonendo`
# con Friendbot, despliega un contrato `adherence` para rehabilitación y otro para
# cadena de frío, los fondea con XLM nativo y escribe sus ids en
# deploy/demo/publisher.json. Es lo que se ejecutó para versionar la demo; se
# repite para regenerarla con claves propias (ver deploy/demo/README.md).
#
# Variables opcionales:
#   STELLAR_SECRET_KEY  clave secreta de la cuenta (por defecto, la de demostración)
#   STELLAR_SOURCE      alias de la cuenta (por defecto, phonendo)
#   VERIFIER_KEY_FILE   JWK Ed25519 del Verifier (por defecto, verifier_demo_key.json)
#   FONDOS_XLM          XLM que recibe cada contrato (por defecto, 1000)
#   REDESPLEGAR=1       despliega aunque publisher.json ya tenga contratos
# La clave secreta nunca se imprime.
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
RED=testnet
ALIAS="${STELLAR_SOURCE:-phonendo}"
# Cuenta de demostración, pública a propósito: solo existe en testnet y no vale nada.
SECRETO="${STELLAR_SECRET_KEY:-$(sed -n 's/^secret_key = "\(.*\)"$/\1/p' "$AQUI/cuenta_phonendo.toml")}"
CLAVE_VERIFIER="${VERIFIER_KEY_FILE:-$AQUI/verifier_demo_key.json}"
FONDOS_XLM="${FONDOS_XLM:-1000}"
PUBLISHER_JSON="$RAIZ/deploy/demo/publisher.json"
WASM="$RAIZ/contracts/target/wasm32v1-none/release/adherence.wasm"

# 1. Alias de la cuenta (la clave entra por stdin, no por argumentos) y Friendbot.
if ! stellar keys address "$ALIAS" >/dev/null 2>&1; then
    printf '%s' "$SECRETO" | stellar keys add "$ALIAS" --secret-key >/dev/null
fi
CUENTA="$(stellar keys address "$ALIAS")"
echo "Cuenta $ALIAS: $CUENTA"
stellar keys fund "$ALIAS" --network "$RED" >/dev/null 2>&1 || echo "Friendbot: la cuenta ya existía"

# 2. Clave pública del Verifier (hex de 32 bytes) a partir del JWK.
VERIFIER_ID="$(node -e 'console.log(Buffer.from(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).x,"base64url").toString("hex"))' "$CLAVE_VERIFIER")"
echo "Verifier: $VERIFIER_ID"

# 3. Contratos ya registrados: no se redespliega salvo REDESPLEGAR=1.
YA="$(node -e 'const c=require(process.argv[1]);console.log(c.contracts&&c.contracts[process.argv[2]]&&c.devices["simulated-cold-chain"]?"si":"no")' "$PUBLISHER_JSON" "$VERIFIER_ID")"
if [ "$YA" = "si" ] && [ "${REDESPLEGAR:-0}" != "1" ]; then
    echo "publisher.json ya tiene contratos para este Verifier (REDESPLEGAR=1 para forzar)"
    exit 0
fi

[ -f "$WASM" ] || (cd "$RAIZ/contracts" && stellar contract build)
TOKEN="$(stellar contract id asset --asset native --network "$RED")"
VK="$RAIZ/circuits/build/soroban_vk.json"

desplegar() {  # $1 = fichero de política
    stellar contract deploy --wasm "$WASM" --source "$ALIAS" --network "$RED" -- \
        --admin "$CUENTA" --verifier_key "$VERIFIER_ID" --token "$TOKEN" \
        --policy-file-path "$1" --verification_key-file-path "$VK" | tail -n 1
}
fondear() {  # $1 = id del contrato
    stellar contract invoke --id "$TOKEN" --source "$ALIAS" --network "$RED" -- \
        transfer --from "$CUENTA" --to "$1" --amount "$((FONDOS_XLM * 10000000))" >/dev/null
}

REHAB="$(desplegar "$RAIZ/contracts/policy.json")"
FRIO="$(desplegar "$RAIZ/contracts/policy_cold_chain.json")"
fondear "$REHAB"
fondear "$FRIO"
echo "Rehabilitación: $REHAB"
echo "Cadena de frío: $FRIO"

# 4. Ids en la configuración del Publisher.
node -e '
const fs = require("fs");
const [ruta, verifier, rehab, frio] = process.argv.slice(1);
const c = JSON.parse(fs.readFileSync(ruta, "utf8"));
c.contracts = { [verifier]: rehab };
c.devices["simulated-cold-chain"].contractId = frio;
fs.writeFileSync(ruta, JSON.stringify(c, null, 2) + "\n");
' "$PUBLISHER_JSON" "$VERIFIER_ID" "$REHAB" "$FRIO"
echo "Escrito $PUBLISHER_JSON"
