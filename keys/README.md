# Claves

Todo lo secreto de Phonendo vive aquí y nunca entra en git (solo este README).

```text
keys/
├── verifiers/<nombre>.json        # clave ed25519 con la que firma un Verifier
└── stellar/identity/<alias>.toml  # cartera Stellar de un Publisher (formato de la Stellar CLI)
```

- **Verifier**: solo firma eventos y lotes. No tiene cartera. Su clave pública en hex
  es el `verifierId` y la que guarda el contrato al desplegarse.
- **Publisher**: su cartera envía `claim()` y paga las comisiones. No firma datos.

```sh
./tools/keys.sh init                     # crea lo que falte: Verifier "dev" y cartera "phonendo"
./tools/keys.sh ls                       # lista claves y carteras (solo la parte pública)
./tools/keys.sh verifier new verifier-b  # nueva clave de Verifier e indica cómo desplegar su contrato
./tools/keys.sh wallet new publisher-b   # nueva cartera, fondeada en testnet
./tools/keys.sh wallet add publisher-b   # guarda una clave secreta S... que ya tengas
```

`init` aprovecha las claves anteriores si existen (`circuits/build/verifier_dev_key.json`
y la cartera `phonendo` de la Stellar CLI). Para usar una cartera con la CLI:
`stellar --config-dir keys/stellar ... --source <alias>`.
