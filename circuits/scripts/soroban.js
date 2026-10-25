// Convierte la prueba y la clave de verificación al formato del verificador
// Groth16 BLS12-381 de Soroban: puntos sin comprimir en big-endian (hex).
const fs = require("fs");
const path = require("path");

const BUILD = path.resolve(__dirname, "..", "build");

function fq(value) {
    return BigInt(value).toString(16).padStart(96, "0");
}

function g1([x, y]) {
    return fq(x) + fq(y);
}

// Fp2 se serializa como c1 || c0; snarkjs lo da como [c0, c1].
function g2([[x0, x1], [y0, y1]]) {
    return fq(x1) + fq(x0) + fq(y1) + fq(y0);
}

function read(name) {
    return JSON.parse(fs.readFileSync(path.join(BUILD, name), "utf8"));
}

const vkey = read("verification_key.json");
const proof = read("proof.json");
const publicSignals = read("public.json");

const args = {
    verification_key: {
        alpha: g1(vkey.vk_alpha_1),
        beta: g2(vkey.vk_beta_2),
        gamma: g2(vkey.vk_gamma_2),
        delta: g2(vkey.vk_delta_2),
        ic: vkey.IC.map(g1),
    },
    proof: {
        a: g1(proof.pi_a),
        b: g2(proof.pi_b),
        c: g1(proof.pi_c),
    },
    public_inputs: publicSignals,
};

fs.writeFileSync(path.join(BUILD, "soroban_args.json"), JSON.stringify(args, null, 2));
console.log("Argumentos de verify_proof en build/soroban_args.json");
