// Compila los circuitos y genera las claves Groth16 sobre BLS12-381.
const { execFileSync } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const snarkjs = require("snarkjs");
const { getCurveFromName } = require("ffjavascript");

const ROOT = path.resolve(__dirname, "..");
const BUILD = path.join(ROOT, "build");
const PTAU_POWER = 12;

function compile(name, flags) {
    execFileSync("circom", [`${name}.circom`, ...flags, "-p", "bls12381", "-o", BUILD], {
        cwd: ROOT,
        stdio: "inherit",
    });
}

function entropy() {
    return crypto.randomBytes(32).toString("hex");
}

async function main() {
    fs.mkdirSync(BUILD, { recursive: true });
    compile("range_adherence", ["--r1cs", "--wasm"]);
    compile("commit", ["--wasm"]);

    const curve = await getCurveFromName("bls12381");
    const ptau0 = path.join(BUILD, "pot_0000.ptau");
    const ptau1 = path.join(BUILD, "pot_0001.ptau");
    const ptau = path.join(BUILD, "pot_final.ptau");
    await snarkjs.powersOfTau.newAccumulator(curve, PTAU_POWER, ptau0);
    await snarkjs.powersOfTau.contribute(ptau0, ptau1, "phonendo", entropy());
    await snarkjs.powersOfTau.preparePhase2(ptau1, ptau);
    await curve.terminate();

    const zkey0 = path.join(BUILD, "range_adherence_0000.zkey");
    const zkey = path.join(BUILD, "range_adherence.zkey");
    await snarkjs.zKey.newZKey(path.join(BUILD, "range_adherence.r1cs"), ptau, zkey0);
    await snarkjs.zKey.contribute(zkey0, zkey, "phonendo", entropy());

    const vkey = await snarkjs.zKey.exportVerificationKey(zkey);
    fs.writeFileSync(path.join(BUILD, "verification_key.json"), JSON.stringify(vkey, null, 2));
    for (const file of [ptau0, ptau1, zkey0]) fs.rmSync(file);
    console.log("Claves generadas en build/");
}

main().then(() => process.exit(0), (err) => {
    console.error(err);
    process.exit(1);
});
