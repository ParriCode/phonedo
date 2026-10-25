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

```sh
npm install
npm run setup                          # compila y genera las claves en build/
npm run prove                          # prueba inputs/session.json y la verifica
npm run prove -- inputs/session_fail.json   # lote fuera de rango: no hay prueba
npm run soroban                        # build/soroban_args.json para verify_proof
```

`soroban_args.json` contiene la clave de verificación, la prueba y las entradas
públicas en el formato del verificador Groth16 BLS12-381 de
[soroban-examples](https://github.com/stellar/soroban-examples/tree/main/groth16_verifier).
La ceremonia de `setup` es de un solo participante y solo vale para desarrollo.
