// Firma de desarrollo del lote, como la hará el Verifier de Phonendo:
// ed25519(commitment || sessionId en 32 bytes || clave de la cuenta G de la paciente).
// Uso: node scripts/sign.js <cuenta G de la paciente>
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const BUILD = path.resolve(__dirname, "..", "build");
// Clave del Verifier en keys/verifiers (./tools/keys.sh); VERIFIER_KEY elige otra.
const KEY_FILE = path.resolve(__dirname, "../../keys/verifiers", `${process.env.VERIFIER_KEY || "dev"}.json`);
const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

// Clave pública de 32 bytes de una dirección G (strkey en base32).
function accountKey(address) {
    if (!/^G[A-Z2-7]{55}$/.test(address)) throw new Error(`Cuenta G no válida: ${address}`);
    let bits = "";
    for (const char of address) bits += BASE32.indexOf(char).toString(2).padStart(5, "0");
    const bytes = Buffer.from(bits.match(/.{8}/g).map((byte) => parseInt(byte, 2)));
    return bytes.subarray(1, 33);
}

function loadKey() {
    if (!fs.existsSync(KEY_FILE)) throw new Error(`Falta ${KEY_FILE}: créala con ./tools/keys.sh init`);
    const jwk = JSON.parse(fs.readFileSync(KEY_FILE, "utf8"));
    return {
        privateKey: crypto.createPrivateKey({ key: jwk, format: "jwk" }),
        publicKey: Buffer.from(jwk.x, "base64url"),
    };
}

const patient = process.argv[2];
if (!patient) throw new Error("Uso: node scripts/sign.js <cuenta G de la paciente>");

const args = JSON.parse(fs.readFileSync(path.join(BUILD, "soroban_args.json"), "utf8"));
const session = Buffer.from(BigInt(args.session_id).toString(16).padStart(64, "0"), "hex");
const { privateKey, publicKey } = loadKey();
const message = Buffer.concat([Buffer.from(args.commitment, "hex"), session, accountKey(patient), publicKey]);

console.log(`verifier_key: ${publicKey.toString("hex")}`);
console.log(`signature:    ${crypto.sign(null, message, privateKey).toString("hex")}`);
console.log(`commitment:   ${args.commitment}`);
console.log(`session_id:   ${args.session_id}`);
