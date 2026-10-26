// Genera y verifica en local la prueba de adherencia de un lote.
// Uso: node scripts/prove.js [inputs/session.json]
const fs = require("fs");
const path = require("path");
const snarkjs = require("snarkjs");
const { useSingleThreadCurve, run } = require("./curve");

const ROOT = path.resolve(__dirname, "..");
const BUILD = path.join(ROOT, "build");
// PROOF_DIR: carpeta propia de cada prueba, para que varios Publishers no se pisen.
const OUT = process.env.PROOF_DIR ? path.resolve(process.env.PROOF_DIR) : BUILD;

async function computeCommitment(batch) {
    const builder = require(path.join(BUILD, "commit_js", "witness_calculator.js"));
    const wasm = fs.readFileSync(path.join(BUILD, "commit_js", "commit.wasm"));
    const calculator = await builder(wasm);
    const witness = await calculator.calculateWitness({
        readings: batch.readings,
        salt: batch.salt,
        sessionId: batch.sessionId,
    }, true);
    return witness[1].toString();
}

async function main() {
    const inputFile = path.resolve(process.argv[2] || path.join(ROOT, "inputs", "session.json"));
    const batch = JSON.parse(fs.readFileSync(inputFile, "utf8"));
    await useSingleThreadCurve();

    const commitment = await computeCommitment(batch);
    let result;
    try {
        result = await snarkjs.groth16.fullProve(
            batch,
            path.join(BUILD, "range_adherence_js", "range_adherence.wasm"),
            path.join(BUILD, "range_adherence.zkey"),
        );
    } catch (err) {
        if (String(err.message).includes("Assert Failed")) {
            throw new Error("El lote no cumple la condición: no se puede generar la prueba");
        }
        throw err;
    }
    const { proof, publicSignals } = result;
    if (publicSignals[0] !== commitment) {
        throw new Error("El compromiso de la prueba no coincide con el del lote");
    }

    const vkey = JSON.parse(fs.readFileSync(path.join(BUILD, "verification_key.json"), "utf8"));
    const valid = await snarkjs.groth16.verify(vkey, publicSignals, proof);
    fs.writeFileSync(path.join(OUT, "proof.json"), JSON.stringify(proof, null, 2));
    fs.writeFileSync(path.join(OUT, "public.json"), JSON.stringify(publicSignals, null, 2));

    const [, minValue, maxValue, minCount, sessionId] = publicSignals;
    console.log(`Compromiso: ${commitment}`);
    console.log(`Sesión ${sessionId}: al menos ${minCount} lecturas en [${minValue}, ${maxValue}]`);
    console.log(valid ? "Prueba válida" : "Prueba NO válida");
    if (!valid) process.exitCode = 1;
}

run(main);
