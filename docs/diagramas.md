# Phonendo diagrams

Updated: 26/10/2026.

| Diagram | Source | SVG | PNG |
| --- | --- | --- | --- |
| Phonendo: services, proof and payment on Stellar | [PlantUML](phonendo.plantuml) | [SVG](phonendo.svg) | [PNG](phonendo.png) |
| Phonendo: from reading to payment | [PlantUML](phonendo-secuencia.plantuml) | [SVG](phonendo_secuencia.svg) | [PNG](phonendo_secuencia.png) |
| Python Reader: classes | [PlantUML](reader.plantuml) | [SVG](reader.svg) | [PNG](reader.png) |

**Architecture.** Reader, Manager, Verifier and Storage form the verification pipeline.
The Publisher subscribes to the Manager's stream, asks the Verifier (through the Manager)
to sign each 5-reading batch and calls `claim()` on the Soroban contract, which pays
in USDC and emits `SessionPaid` for the web panels. There is one contract per use case
(rehabilitation and cold chain); readings never leave Phonendo.

**Sequence.** Every reading is verified and stored; every 5 readings of one device are
proved, signed and claimed. The contract checks, in order, that the session was not
paid before, the Verifier's ed25519 signature and the Groth16 proof against the policy
stored on-chain.

**Reader.** Domain, outputs (SSE stream and HTTP push to Managers) and the optional
HTTP server of the Python Reader. The C++ core and the ESP32 example emit the same events.

Current sources: `apps/reader/python/`, `apps/manager/`, `apps/verifier/`,
`apps/storage/main.py`, `apps/publisher/`, `contracts/adherence/src/lib.rs` and
`tests/integration/test_pipeline.py`.

Render with PlantUML (UTF-8), for example:

```sh
plantuml -charset UTF-8 -tsvg docs/*.plantuml
plantuml -charset UTF-8 -tpng docs/*.plantuml
```
