# AGENTS.md

Context for any AI agent (Claude, Codex, Cursor, Copilot...) working in this repo.
Read it before changing code. If something here contradicts the code, trust the
code and flag the mismatch.

## Goal

Win HackMeridian 2026 (Stellar hackathon, Lisbon) with **Phonendo on Stellar**:
prove that health sensor data meets a condition **without revealing the data**,
verify that proof in a Soroban contract and pay automatically in USDC.

- Builder track: **Genesis** (early project; the MVP must run on Stellar testnet).
- Thematic tracks: **Stellar Unlocked** (ZK proof verified in Soroban with native
  host functions) and **Stellar Composed** (ZK + USDC payments combined).
- Prize pool: 30,000 USD for 6 winners, paid in XLM.

## Use case

**Main (A): cardiac rehabilitation adherence.** An insurer pays the patient a
small USDC reward for each completed rehab session. A session counts when the
heart rate stayed inside the doctor's zone (e.g. 90-130 bpm) for enough readings.
The insurer only sees "session met ✓" and the payment, never the pulse.
Why the insurer pays: patients who drop out of rehab are readmitted more often,
and readmissions cost far more than the reward. Phonendo charges a fee per
verified proof.

**Backup (B): cold chain.** Same circuit and contract with a DHT11 temperature
sensor: a buyer pays when a shipment stayed in range. Only the policy values change.

The circuit is a template: min, max and required count are public parameters,
so one deployment serves different policies without new code.

## How the jury scores (apply it to every decision)

| Criterion | Weight | What it means for code and demo |
| --- | --- | --- |
| Track alignment | 20 | Fit with Unlocked and Composed. One `claim()` that uses Stellar natively: Groth16 pairing check, ed25519 signature check, USDC payment. README table "native feature -> where it is used". |
| User value / problem | 20 | Clear payer (insurer) and payee (patient). Health data is special-category data under GDPR, hence ZK. |
| Technical execution | 15 | It works end to end on testnet. Contract tests: valid proof, tampered proof, session already claimed, forged signature. Contract IDs and tx hashes in the README. Clean repo, no keys. |
| Innovation | 15 | ZK over real signed sensor data on Stellar, with the proof bound to verified data (see binding below). |
| Hackathon progress | 10 | Small, frequent, meaningful commits. List of what was built at the event (see Built at the event). |
| Market / ecosystem | 10 | Customer (insurers), revenue (fee per verified proof), why now (native ZK on Stellar), and a clear next-steps roadmap (Genesis values potential to continue). |
| Design / UX | 10 | One screen, two columns: patient (own chart) and insurer (only ✓, amount, stellar.expert link). A "Simulate session" button in case the sensor fails. |

Prefer the change that moves a high-weight criterion and keeps the demo
reliable. A working, honest end-to-end flow beats extra features.

## Architecture

Existing services (Python, in `apps/`):

| Service | Role |
| --- | --- |
| Reader | Reads devices/sensors and exposes observations over SSE. Python and C++ cores, Linux (simulated) and Arduino/ESP examples. |
| Manager | Coordinates the flow, computes the HMAC-SHA256 `managerHash`, retries on timeout. |
| Verifier | Validates fields, time and hash; signs each Verified event and, on `POST /signBatch`, the batch commitment, both with one ed25519 key. |
| Storage | Stores Verified events in LevelDB and organises its own database. Raw data stays off-chain here. |
| Publisher | Listens only to the Manager `/stream`, batches 5 Verified readings per device, proves with `circuits/`, signs and calls `claim()` through the Stellar CLI. |

El Manager evita conexiones HTTP/SSE redundantes por servicio, no observaciones
repetidas. Para Reader conserva el primer transporte seleccionado hasta reiniciar;
para Verifier y Storage prioriza el HTTP configurado y rechaza SSE redundante (409).
Los suscriptores Verifier/Storage se identifican con `server.publicUrl` y
`X-Phonendo-Service-URL`; usar la misma URL canónica que en el Manager.
Hay logs de selección/rechazo y pruebas en `tests/app_tests/test_manager_transports.py`.

Monitorización simple en los cinco servidores Python: `/info` devuelve una lista
de `peer`/`transport`; `/logs`, hasta 200 mensajes en memoria. Ambas sin token.
SSE refleja conexiones activas; HTTP, destinos configurados o clientes recibidos.

New pieces: `circuits/` (Circom + snarkjs) and a Soroban contract in Rust.

`tools/web.sh` sirve el operador con `tools/web_runtime.py` (aiohttp local).
Crea Readers reales en memoria, gestiona dispositivos/sensores y pulsos; configura
push HTTP/SSE y tokens en vivo. Consulta logs externos mediante un puente local
limitado a IPs privadas/loopback. Los servicios externos no se editan. La web
(`apps/web`) es React + Vite con providers/consumers (`src/providers`): el operador
(`OperatorProvider`) muestra únicamente confirmaciones observadas. El canvas es
`src/components/canvas`; su lógica pura (modelos, estado, layout, geometría y API)
sigue en `apps/web/service_network/` con sus tests. Conserva posiciones/viewport por
despliegue; el polling no mueve el lienzo.

End-to-end flow:

1. Sensor -> Reader -> Manager -> Verifier -> Storage (existing pipeline). Each
   observation carries `readerId` and `deviceId`; there is no device registration.
2. Publisher (subscribed to the Manager `/stream`; it talks to no other service)
   groups 5 Verified readings of a session and picks a random `salt`. It ignores
   events of Verifiers it does not serve. `sessionId` = first 63 bits of
   SHA-256 of the sorted `eventKeys`; the Verifier rejects any other value and
   never signs one event in two sessions, so the same readings are always the
   same session and the contract never pays them twice, whatever the number of
   Publishers. Each proof is written to its own folder (`PROOF_DIR`).
3. Publisher -> Manager `POST /signBatch` -> Verifier `POST /signBatch` with only
   `sessionId`, `salt`, `patient` and the 5 `eventKeys`. The Verifier takes the
   readings from its own memory of events it verified (never from the caller),
   computes `Poseidon(sessionId, salt, readings)` in Python
   (`apps/verifier/verifier_support/poseidon.py`, identical to the circuit) and
   signs it with **ed25519** (Soroban verifies ed25519 natively; it cannot verify
   RSA). The same key also signs each Verified event (`verifierSign`). Signed
   message (128 bytes):
   `commitment (32 B, big-endian) || sessionId (32 B, big-endian) || ed25519
   public key of the patient's G account (32 B) || verifierId (32 B)`. The key is
   `keys/verifiers/<name>.json` (gitignored JWK; `dev` is the key the deployed
   contracts trust). `circuits/scripts/sign.js` is the reference
   implementation. The Publisher never signs by itself.
4. The Publisher rejects the signature if the returned commitment differs from
   the one in its proof.
5. Publisher generates a Groth16 proof with `range_adherence.circom`: the private
   readings produce that commitment and at least `minCount` are in
   `[minValue, maxValue]`.
6. Publisher calls `claim(patient, session_id, commitment, signature, proof)`.
   It checks, in order: that `sessionId` was not claimed before (anti-replay);
   the ed25519 signature against the Verifier key stored at deploy; the proof
   against the stored verification key, with `minValue`, `maxValue`, `minCount`
   taken from the policy stored on-chain (never from the caller). Then it marks
   the session as claimed, transfers the payout from the contract balance funded
   by the insurer to `patient` and emits `SessionPaid`. Anyone may submit the
   claim: `patient` is inside the signed message, so only the Verifier decides
   who gets paid.
7. The dashboard reads contract events and links the tx on stellar.expert.

Identidad: `managerId + verifierId + readerId + observationId`; `verifierId` es
la clave pública ed25519 hex. Publisher separa lotes por Manager/Verifier/Reader/
dispositivo, conserva la URL/token del SSE de origen y pide `signBatch` a ese
Manager indicando Verifier y Reader. El Manager descubre `/metadata` de sus
Verifiers HTTP y selecciona la identidad indicada. Un mismo Verifier puede servir
a varios Managers. Publisher configura `contracts: {"<verifierId>": "<contractId>"}`.
El mensaje firmado nuevo requiere redesplegar los contratos anteriores.

On-chain: only the commitment, public parameters, session id, proof result and
payment. Never readings or personal data.

Honest limits (say them in the pitch): we trust the Phonendo Verifier and the
sensor. Next step: the ESP32 signs each reading itself (P-256).

## Repo layout

```text
phonedo/
├── apps/                 # Python services, one folder each, own Dockerfile and README
│   ├── reader/           # python/ and cpp/ cores + servers; examples/linux (simulated), examples/arduino
│   ├── manager/          # flow coordination, managerHash, retries
│   ├── verifier/         # validation and signature of Verified events
│   ├── storage/          # LevelDB store of Verified events
│   ├── publisher/        # batches Verified readings, proves and calls claim()
│   └── web/              # React + Vite: portada, operador, paciente y aseguradora; providers compartidos, pagos del RPC de testnet
├── circuits/             # Circom circuits, inputs/ examples, scripts/ (setup, prove, soroban)
├── contracts/            # Soroban contract `adherence` (Rust): claim() verifies signature + proof and pays
├── deploy/
│   ├── docker/           # compose.yml and per-service JSON config
│   └── env/              # dev.env for local runs
├── docs/                 # PlantUML diagrams (.plantuml + .png/.svg) and presentacion.html
├── keys/                 # gitignored secrets (README only): verifiers/ signing keys, stellar/ wallets
├── tests/                # app_tests/, integration/, arduino_uno_test/
└── tools/                # keys.sh, configs, tests and operator console (web.sh --regenerate-keys --rebuild)
```

Generated folders (`circuits/build/`, `node_modules/`, `target/`, `.venv/`) are
local only. All are in `.gitignore` (`contracts/.gitignore` covers `target/` and `test_snapshots/`).

## Built at the event

List it in the README and the pitch.

| Piece | What it does |
| --- | --- |
| ZK circuit and proving scripts (`circuits/`) | Groth16 proof that at least N readings are in range |
| Publisher | Batching, proof, batch signature, `claim()` call |
| Verifier | One ed25519 key signs events and the batch commitment |
| Soroban contract | Groth16 verification, anti-replay, USDC payout |
| Web panels | Operator console, rehab, cold-chain and company panels |

## Stellar and ZK decisions (verified)

- Proof system: **Groth16 on BLS12-381**, verified with the official example
  `stellar/soroban-examples/groth16_verifier` (BLS12-381 host functions, CAP-59).
  Circom defaults to BN254, so always compile with `-p bls12381`.
- Already checked: proofs from `circuits/` pass in snarkjs and in the official
  verifier's tests (a tampered signal is rejected).
- `npm run soroban` writes `build/soroban_args.json` in the verifier's format:
  G1 = `x||y`, G2 = `x.c1||x.c0||y.c1||y.c0`, uncompressed big-endian hex;
  public inputs as decimal strings.
- Public signal order (`public.json`): `[commitment, minValue, maxValue, minCount, sessionId]`.
  The contract must use the same order.
- Poseidon inside the circuit uses circomlib's constants over the BLS12-381
  field. Fine for the hackathon, not standard parameters, and not the same as
  Stellar's native Poseidon host function, so the contract does not recompute
  the commitment; it trusts the signed value and the proof.
- Readings are integers 0-255 (8 bits). Encode other units to fit (e.g.
  temperature with an offset).
- The `setup` ceremony is single-party: development only, say so in the README.
- `setup` and `prove` force a single-thread curve (`scripts/curve.js`): on
  Windows the snarkjs workers died silently. `setup` takes about 5 minutes.
- Network: **testnet**. Asset: **USDC from Circle** (testnet faucet:
  faucet.circle.com), issuer `GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5`.
  Get its contract id with
  `stellar contract id asset --asset USDC:<issuer> --network testnet`.
- Keys: everything secret lives in `keys/` (gitignored, managed by
  `tools/keys.sh`). The Verifier has an ed25519 signing key and no wallet
  (`keys/verifiers/<name>.json`); the Publisher has a Stellar wallet and signs
  no data (`keys/stellar/identity/<alias>.toml`, Stellar CLI format, used with
  `--config-dir keys/stellar --source <alias>`). Docker and the operator mount
  only the key or wallets each container needs, read-only. Never write secret
  keys or seed phrases in code, config, docs or commits. A secret of the
  `phonendo` wallet was committed once (`deploy/docker/.env.example`, removed):
  it counts as leaked.
- The Circle faucet first gave no testnet USDC, so the first claim paid native XLM.
  USDC arrived later on 25 Oct and the USDC instance is funded (20 USDC).
  Same wasm; only the `token` argument of the deploy changes.
- In the pitch, name the curve we use (BLS12-381), not BN254.

## Testnet deployments

| What | Value |
| --- | --- |
| `adherence`, paying XLM (used for the first claim) | `CAPZ2O7LPTRGJ2Q7TTHMCHOKRZ4T7KU5I4E74M2U3YUTC3XONIQDOP2D` |
| `adherence`, paying USDC, 5-reading batches (rehabilitation, 4 of 5, 0.1 USDC per session; used by the Publisher) | `CCLQFKRWBLRSPLVAFWBLG22LPRGP3GEV47CGXA6C3VAGPQ2QITE3DNYL` |
| `adherence`, paying USDC, 32-reading batches (retired: its Verifier key is not on this machine) | `CD3ZLDTB7QKJLMAIBSCL75TRHE6IUZ27RW5FLWNB4F3GUQENZZZSM45H` |
| `adherence`, paying USDC, previous signature format (retired) | `CBF2MBQ6W4S6LD3JSIM3NNZET5KBUKOADRZSKIYZRZBAXRM6OJZCNSFI` |
| First on-chain claim (proof + signature verified, 5 XLM paid) | `891b2fe1504a9d9c0a34146828e9caac9527a41e3d467eaecf5a994c145c0aa1` |
| Fund the USDC contract (20 USDC) | `f791426c649045fc02dfbbf7cc69d1b6796292d53da0a4455a6499a0657dc4fa` |
| First USDC claim (manual, 5 USDC paid) | `0ba0adb7ca42e09350f71eec15c09d252dcfacf13b6cc3672afab8017ce78033` |
| First end-to-end USDC claim (simulated pulse Reader through the Publisher) | `2a345e9fdf594fc385107a2e1a2e973d3cb16f5274fc14e763bbe9dc0406ef47` |
| `adherence` for cold chain (2-8 °C, 5 of 5, USDC, same Verifier key) | `CACUZG5V45NPFFB5JSLHMTF6NHEP5GMGZ5QJKJPET4ZIRTWOW6VS2VQS` |
| `adherence` for cold chain, 32-reading batches (retired) | `CDNPBN6HZP4PZKRFOOA2PYC772KF4THXTJNKHBS5Y33HCAVDWCVO5SRE` |
| First cold-chain claim (simulated temperature Reader through the Publisher, 5 USDC) | `639fcfddd74ddcd1344a26cd1638ac5f66e12a7bc2f69be04da8fb7815a9efb6` |

Both trust the Verifier key `keys/verifiers/dev.json` (`d407a2…`), have admin `phonendo` and pay 0.1 USDC (rehabilitation 90-130 bpm, 4 of 5 readings; cold chain 2-8 °C, 5 of 5). Check it with `./tools/keys.sh verifier check <contract>`. The old payout was 5 units, and the
development Verifier key `keys/verifiers/dev.json`. A new
`npm run setup` makes new circuit keys: redeploy the contract with the new
`soroban_vk.json` after it.
- When unsure about Soroban/Stellar APIs, check the official docs
  (developers.stellar.org) or the Stellar Raven MCP before writing code.

## Commands

Public web demo (Vercel, project `phonendo`): https://phonendo.vercel.app. Redeploy from
`apps/web` with `npm run build && npx vercel deploy dist --prod`; the repo is not
connected to Vercel. The operator console works only locally.
Demo video (YouTube): https://youtu.be/nX8ho0uSeZE

Local stack (Docker, simulated Reader and Publisher; ports 7101-7105):

```sh
docker compose -f deploy/docker/compose.yml up --build -d --wait
curl http://127.0.0.1:7104/raw        # Verified events in Storage
docker compose -f deploy/docker/compose.yml down
```

Tests of the existing services: see the root `README.md`
(`./tools/test.sh`, `./tools/test_integration.sh`, `./tools/test_docker.sh`).

Circuit (needs Node.js and `circom` 2.2 in PATH):

```sh
cd circuits
npm install
npm run setup                               # compile + dev keys in build/
npm run prove                               # proves inputs/session.json
npm run prove -- inputs/session_fail.json   # out of range: no proof
npm run prove -- inputs/cold_chain.json     # cold chain: 5 of 5 readings in 2-8 °C
npm run soroban                             # build/soroban_*.json for the contract
node scripts/sign.js <G account>            # dev signature of the batch (VERIFIER_KEY=dev)
```

Contract (Rust, soroban-sdk, Stellar CLI, `rustup target add wasm32v1-none`;
full deploy and claim steps in `contracts/README.md`):

```sh
stellar contract build
cargo test
stellar contract deploy --wasm <file.wasm> --source <alias> --network testnet
stellar contract invoke --id <contract_id> --source <alias> --network testnet --send=no -- <fn> ...
```

`--send=no` only simulates: use it to check cost before sending.

## Repo rules

- The repo will be judged: keep it clean. No stray files, no notes or summaries,
  no generated artifacts. `circuits/build/`, `node_modules/`, `target/`,
  `.wasm`, `.zkey`, `.ptau` stay out of git.
- No secrets in git: no private keys, seeds, tokens or personal paths.
  `keys/` and `config.env` are gitignored and generated by `tools/keys.sh` and
  `tools/generate_configs.sh`; the old RSA `keys.json` (removed) was in git
  history, so it counts as leaked. Never commit files like them.
- Match the existing style. Code comments, READMEs and user-facing messages are
  in **Spanish**; keep them short. Follow each service's current structure.
- Small, focused changes. Do not refactor or reformat code you were not asked to touch.
- Tests: when you add or change behaviour, add a test that covers it if it makes
  sense (skip trivial changes such as docs or config). Put it where similar tests
  live: Python services in `tests/app_tests/` (pytest), cross-service flows in
  `tests/integration/`, the contract as Rust `#[test]`s inside the contract crate
  (`cargo test`), the circuit with an extra case in `circuits/inputs/`. Run the
  related tests before saying a change is done, and never delete or skip a test
  to make it pass.
- Never add AI co-authors or AI attribution to commits (`Co-Authored-By` etc.).
  Do not commit or push unless the human asks.
- The final README must include: summary, problem, setup, environment
  variables, demo steps, architecture with how Stellar is used, contract IDs,
  at least one testnet tx hash, and a clear list of what
  was built at the event.

## Out of scope (next steps)

Do not build these; they close the pitch as the roadmap:
signing on the ESP32, decentralised storage, anchors / fiat off-ramp,
confidential tokens, several circuit types, mainnet, a multi-party trusted setup.
