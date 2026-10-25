# Contracts

Contrato Soroban `adherence`: paga en USDC una sesión cuando recibe una prueba
Groth16 válida de `circuits/` y la firma ed25519 del Verifier sobre el lote.

## `claim`

`claim(patient, session_id, commitment, signature, proof)` comprueba, en orden:

1. Que `session_id` no se ha cobrado ya.
2. La firma del Verifier sobre `commitment || session_id (32 bytes) || clave de la cuenta G de patient || verifierId (32 bytes)`.
3. La prueba con las entradas públicas `[commitment, min_value, max_value, min_count, session_id]`,
   donde rango y mínimo salen de la política guardada, no del que llama.
4. Si todo es válido, marca la sesión y transfiere `payout` del contrato a `patient`.

Cualquiera puede enviar el `claim` (por ejemplo el Publisher): el pago siempre va a la
paciente firmada. `policy.json` es la política inicial; `payout` va en unidades de 7
decimales (`1000000` = 0,1 USDC).

`verifierId` es la clave pública ed25519 guardada en el contrato. Cada Verifier
usa su propia instancia, seleccionada en `contracts` del Publisher. Este formato
de firma requiere redesplegar las instancias anteriores.

## Uso

Requiere Rust, el target `wasm32v1-none` y Stellar CLI 25.2 o superior.

```sh
cargo test
stellar contract build
```

### Despliegue en testnet

Desde `circuits/`, con `npm run prove` y `npm run soroban` ya ejecutados:

```sh
node scripts/sign.js <cuenta G de la paciente>
```

Imprime la clave pública del Verifier de desarrollo y la firma del lote. Después,
desde `contracts/`:

```sh
stellar contract id asset --asset USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5 --network testnet

stellar contract deploy --wasm target/wasm32v1-none/release/adherence.wasm --source <cuenta> --network testnet -- \
  --admin <cuenta> --verifier_key <verifier_key> --token <id USDC> \
  --policy-file-path policy.json --verification_key-file-path ../circuits/build/soroban_vk.json

stellar contract invoke --id <id USDC> --source <cuenta> --network testnet -- \
  transfer --from <cuenta> --to <id contrato> --amount 200000000

stellar contract invoke --id <id contrato> --source <cuenta> --network testnet -- \
  claim --patient <cuenta G de la paciente> --session_id <session_id> --commitment <commitment> \
  --signature <signature> --proof-file-path ../circuits/build/soroban_proof.json
```

La paciente necesita trustline de USDC para recibir el pago.

### Cadena de frío

El mismo contrato y el mismo circuito sirven para el transporte refrigerado: solo cambia
la política. Despliega otra instancia con `policy_cold_chain.json` (2 a 8 °C, las 32
lecturas) y la misma clave del Verifier, y añádela a `devices` del Publisher con su
política (ver el README del Publisher). El pago va a la cuenta que cobra por el
dispositivo, en este caso el transportista.

```sh
stellar contract deploy --wasm target/wasm32v1-none/release/adherence.wasm --source <cuenta> --network testnet -- \
  --admin <cuenta> --verifier_key <clave del Verifier> --token <id USDC> \
  --policy-file-path policy_cold_chain.json --verification_key-file-path ../circuits/build/soroban_vk.json
```
