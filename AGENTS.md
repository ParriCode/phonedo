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
- Phonendo paper: Moya et al., *Wireless Networks* (2023),
  doi:10.1007/s11276-023-03458-7.

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
| Hackathon progress | 10 | Small, frequent, meaningful commits. Before/after table (see Prior work). |
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
| Verifier | Validates fields, time and hash; signs the Verified event (RSA today). |
| Storage | Stores Verified events in LevelDB and organises its own database. Raw data stays off-chain here. |
| Publisher | Empty (README + disabled config). This is where the ZK prover and the Stellar call plug in. |

El Manager evita conexiones HTTP/SSE redundantes por servicio, no observaciones
repetidas. Para Reader conserva el primer transporte seleccionado hasta reiniciar;
para Verifier y Storage prioriza el HTTP configurado y rechaza SSE redundante (409).
Los suscriptores Verifier/Storage se identifican con `server.publicUrl` y
`X-Phonendo-Service-URL`; usar la misma URL canónica que en el Manager.
Hay logs de selección/rechazo y pruebas en `tests/app_tests/test_manager_transports.py`.

New pieces: `circuits/` (Circom + snarkjs) and a Soroban contract in Rust.

End-to-end flow:

1. Sensor -> Reader -> Manager -> Verifier -> Storage (existing pipeline). Each
   observation carries `readerId` and `deviceId`; there is no device registration.
2. Publisher groups 32 Verified readings of a session and picks a random `salt`.
3. The batch commitment `Poseidon(sessionId, salt, readings)` is computed with
   `circuits/commit.circom` (its wasm), so it matches the circuit exactly.
4. The Verifier signs the commitment with **ed25519** (Soroban verifies ed25519
   natively; it cannot verify RSA).
5. Publisher generates a Groth16 proof with `range_adherence.circom`: the private
   readings produce that commitment and at least `minCount` are in
   `[minValue, maxValue]`.
6. Publisher calls `claim()` on the contract. It checks, in order: the ed25519
   signature against the registered Verifier key; the proof against the stored
   verification key; that `minValue`, `maxValue`, `minCount` equal the policy
   stored on-chain (never trust caller-supplied policy values); that `sessionId`
   was not claimed before (anti-replay). Then it marks the session as claimed,
   transfers USDC from the contract balance funded by the insurer to the
   patient's registered address (never a caller-supplied address) and emits an event.
7. The dashboard reads contract events and links the tx on stellar.expert.

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
│   └── publisher/        # empty for now: prover + Stellar call go here
├── circuits/             # Circom circuits, inputs/ examples, scripts/ (setup, prove, soroban)
├── contracts/            # Soroban contract in Rust (to be added)
├── deploy/
│   ├── docker/           # compose.yml and per-service JSON config
│   └── env/              # dev.env for local runs
├── docs/                 # PlantUML diagrams (.plantuml + .png/.svg) and overview.md
├── tests/                # app_tests/, integration/, docker/, arduino_uno_test/
└── tools/                # dev, build, test and lab scripts (lab.sh = UI lab)
```

Generated folders (`circuits/build/`, `node_modules/`, `target/`, `.venv/`) are
local only. All are in `.gitignore` except `target/`: add it together with the contract.

## Prior work

Declare it in the README and the pitch. Phonendo existed before the event as an
academic prototype (paper above) that published to IOTA, with no Stellar, ZK or
payment code. Everything Stellar is built at the event.

| Before the event | Built at the event |
| --- | --- |
| Reader, Manager, Verifier, Storage (Python), Docker stack, tests | ZK circuit and proving scripts (`circuits/`) |
| Publisher as an empty placeholder | Publisher: batching, commitment, proof, `claim()` call |
| Verifier signs with RSA | ed25519 signature of the batch commitment |
| Publishing to IOTA (paper) | Soroban contract: Groth16 verification, anti-replay, USDC payout |
| No user interface for the use case | Patient / insurer dashboard |

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
- Network: **testnet**. Asset: **USDC from Circle** (testnet faucet:
  faucet.circle.com), issuer `GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5`.
  Get its contract id with
  `stellar contract id asset --asset USDC:<issuer> --network testnet`.
- Accounts: use Stellar CLI key aliases (`--source <alias>`). Never write
  secret keys or seed phrases in code, config, docs or commits.
- In the pitch, name the curve we use (BLS12-381), not BN254.
- When unsure about Soroban/Stellar APIs, check the official docs
  (developers.stellar.org) or the Stellar Raven MCP before writing code.

## Commands

Local stack (Docker, simulated Reader; ports 7101-7104):

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
npm run soroban                             # build/soroban_args.json
```

Contract (Rust, soroban-sdk, Stellar CLI):

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
  `apps/verifier/keys.json` and the `config.env` files are currently tracked
  even though `.gitignore` lists `config.env`; they must leave the repo (rotate
  the key), so do not add more files like them.
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
  at least one testnet tx hash, and a clear split between prior work and what
  was built at the event.

## Out of scope (next steps)

Do not build these; they close the pitch as the roadmap:
signing on the ESP32, decentralised storage, anchors / fiat off-ramp,
confidential tokens, several circuit types, mainnet, a multi-party trusted setup.
