# Publisher

Cobra en Stellar las sesiones que cumplen la política, sin publicar las lecturas.
Escucha el `/stream` del Manager, junta las lecturas Verified de cada dispositivo
en lotes de `batchSize` (32), genera la prueba ZK con `circuits/`, firma el lote y
llama a `claim()` del contrato `contracts/adherence`.

## Flujo por lote

1. Toma `payload.simple_result` de cada evento Verified, redondeado a un entero de 0 a 255.
   Cada evento cuenta una vez aunque el stream lo repita.
2. Al completar el lote asigna `sessionId` (inicio del lote en ms) y una sal aleatoria.
3. `node scripts/prove.js` y `node scripts/soroban.js` en `circuits/` generan la prueba.
   Si el lote no cumple la política no hay prueba y no se cobra.
4. Pide la firma ed25519 de `commitment || sessionId || cuenta G de la paciente` a
   `POST /signBatch` del Manager, que la obtiene del Verifier. Solo envía los ids de
   los eventos; si el commitment firmado no coincide con el de la prueba, no cobra.
5. `stellar contract invoke ... -- claim` con el alias de cuenta configurado.
   Registra en el log el hash de la transacción o el motivo del fallo.

## Endpoints

| Ruta | Uso |
| --- | --- |
| `GET /` | Comprobar que el servicio responde. |
| `GET /info` | Manager conectado por SSE. |
| `GET /logs` | Últimos 200 mensajes. |

## Configuración

`publisher.py` carga `config.env` y arranca en `PORT_PUBLISHER`.
`PUBLISHER_CONFIG_PATH` selecciona el JSON (por defecto `config.json`).

| Campo | Uso |
| --- | --- |
| `subscriptions.managers` | URLs base de los Managers; consume su `/stream` con Bearer `API_TOKEN_MANAGER`. |
| `batchSize`, `policy` | Lecturas por lote y política; debe coincidir con la guardada en el contrato. |
| `patients` | Cuenta G que cobra por `deviceId`; `default` para el resto. |
| `signer.manager` | Manager al que pide la firma del lote; por defecto el primero de `subscriptions.managers`. |
| `stellar` | `contractId`, alias `source` de la CLI y `network`. |

Requiere Node.js con `circuits/` preparado (`npm install`, `npm run setup`,
`node scripts/sign.js <cuenta G>` crea la clave de desarrollo que el Verifier usa como
`signing_key.json`), Stellar CLI con el alias configurado y el contrato desplegado con
la clave pública de esa clave y con esa política. Además, el Manager y el Verifier
deben estar en marcha con `POST /signBatch`. Con el ejemplo de Docker el
Publisher ya se arranca automáticamente:

```sh
docker compose -f deploy/docker/compose.yml up --build -d --wait
curl http://127.0.0.1:7105/info
```

El Reader simulado de Docker emite pulso de 95 a 120 (`"simulation": "pulse"` en
`deploy/docker/reader.json`), dentro de la política de rehabilitación (90-130). Con
temperaturas de 20 a 30 sus lotes no cumplirían y no se cobrarían.

[Arquitectura general](../../docs/diagramas.md).
