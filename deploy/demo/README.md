# Demo preconfigurada (SOLO TESTNET / CLAVES DE DEMOSTRACIÓN)

Con `docker compose -f deploy/docker/compose.yml up --build -d --wait` el sistema cobra
solo en Stellar testnet: Reader simulado, Manager, Verifier, Publisher, `claim()` y
evento `SessionPaid`, para rehabilitación y cadena de frío.

## Qué es de demostración

- **Cuenta `phonendo`** (`GBZCQXYSSUK5ELUXKWQBBNCSIAOBHPGG36THG35QJLSBLF3BBVGKEMGJ`):
  firma el `claim()`, es admin de los contratos y cuenta de despliegue. Su clave secreta
  está en `compose.yml` y en `desplegar_demo.sh`.
- **`verifier_demo_key.json`**: clave Ed25519 (JWK) del Verifier; su pública hex es el
  `verifierId` de `deploy/docker/publisher.json`.
- **`circuits/build/`**: zkey, clave de verificación y wasm de la ceremonia de un solo
  participante. Solo vale para desarrollo. No se versionan los `.ptau` ni las pruebas.
- **Contratos** `adherence` de rehabilitación y cadena de frío, pagando XLM nativo
  (0,1 XLM por sesión), con 1000 XLM de testnet cada uno.

Todas estas claves son públicas y no protegen nada: solo existen en testnet y no valen
dinero. No las uses en mainnet ni reutilices la cuenta.

## Regenerar con claves propias

1. Instala `circom` 2.2 y ejecuta `cd circuits && npm ci && npm run setup`.
2. Genera tu clave de Verifier (JWK `kty`, `crv`, `d`, `x`) y tu cuenta con `stellar keys generate`.
3. Ejecuta, con tus valores:

```sh
STELLAR_SOURCE=mi-cuenta STELLAR_SECRET_KEY=S... VERIFIER_KEY_FILE=ruta/clave.json \
  REDESPLEGAR=1 deploy/demo/desplegar_demo.sh
```

El script fondea la cuenta con Friendbot, despliega los dos contratos, los fondea y
escribe sus ids en `deploy/docker/publisher.json`. Después pon la misma cuenta en
`deploy/docker/.env` y monta tu clave del Verifier en `compose.yml`.
