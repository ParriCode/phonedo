# Circuits

Circuito Groth16 (BLS12-381) que demuestra que un lote de lecturas cumple una
condición sin revelar las lecturas: al menos `minCount` de 32 valores están en
`[minValue, maxValue]`. Sirve igual para pulso en rehabilitación cardíaca o para
temperatura en cadena de frío.

## Señales

| Señal | Tipo | Uso |
| --- | --- | --- |
| `readings[32]` | privada | Lecturas del lote, enteros de 0 a 255. |
| `salt` | privada | Valor aleatorio del lote para que el compromiso no revele las lecturas. |
| `minValue`, `maxValue` | pública | Rango permitido. |
| `minCount` | pública | Lecturas mínimas dentro del rango. |
| `sessionId` | pública | Identificador de la sesión, evita reutilizar una prueba. |
| `commitment` | salida pública | Poseidon de sesión, sal y lecturas; lo firma el Verifier. |

`public.json` queda en el orden `[commitment, minValue, maxValue, minCount, sessionId]`.
`commit.circom` calcula solo el compromiso, para firmar el lote antes de probarlo.

## Uso

Requiere Node.js, `circom` 2.2 en el PATH y las dependencias de `npm install`.
`setup` tarda unos minutos porque trabaja en un solo hilo.

```sh
npm install
npm run setup                          # compila y genera las claves en build/
npm run prove                          # prueba inputs/session.json y la verifica
npm run prove -- inputs/session_fail.json   # lote fuera de rango: no hay prueba
npm run prove -- inputs/cold_chain.json     # cadena de frío: 32 de 32 lecturas entre 2 y 8 °C
npm run soroban                        # argumentos para el contrato en build/
node scripts/sign.js <cuenta G>        # firma de desarrollo del lote
```

`npm run soroban` escribe la clave de verificación (`soroban_vk.json`), la prueba
(`soroban_proof.json`) y todo junto (`soroban_args.json`) en el formato del
contrato de `contracts/`, el mismo que el verificador Groth16 BLS12-381 de
[soroban-examples](https://github.com/stellar/soroban-examples/tree/main/groth16_verifier).
`sign.js` firma el lote como lo hará el Verifier, con una clave de desarrollo que
guarda en `build/`; solo sirve para probar antes de tenerlo integrado.
La ceremonia de `setup` es de un solo participante y solo vale para desarrollo.
