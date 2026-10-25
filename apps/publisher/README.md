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
deben estar en marcha con `POST /signBatch`. Con el ejemplo de Docker:

```sh
cd apps/publisher
pip install -r requirements.txt
API_TOKEN_MANAGER=demo-manager python publisher.py
```

El Reader simulado de Docker emite temperaturas de 20 a 30, así que con la política
de rehabilitación (90-130) sus lotes no cumplen y no se cobran.

[Arquitectura general](../../docs/diagramas.md).
