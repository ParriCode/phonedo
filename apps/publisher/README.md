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
4. Firma con ed25519 `commitment || sessionId || cuenta G de la paciente`, de momento
   con la clave de desarrollo de `circuits/scripts/sign.js`.
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
| `signer.keyPath` | Clave de desarrollo, relativa a `circuitsPath`. |
| `stellar` | `contractId`, alias `source` de la CLI y `network`. |

Requiere Node.js con `circuits/` preparado (`npm install`, `npm run setup`,
`node scripts/sign.js` para crear la clave), Stellar CLI con el alias configurado y
el contrato desplegado con esa clave y esa política. Con el ejemplo de Docker:

```sh
cd apps/publisher
pip install -r requirements.txt
API_TOKEN_MANAGER=demo-manager python publisher.py
```

El Reader simulado de Docker emite temperaturas de 20 a 30, así que con la política
de rehabilitación (90-130) sus lotes no cumplen y no se cobran.

[Arquitectura general](../../docs/diagramas.md).
