// snarkjs reparte el trabajo en workers de ffjavascript. En Windows esos workers
// pueden morir sin avisar y Node termina sin error a mitad de proceso, así que
// se usa una sola curva BLS12-381 en un hilo, que snarkjs reutiliza.
const { buildBls12381 } = require("ffjavascript");

async function useSingleThreadCurve() {
    const curve = await buildBls12381(true);
    globalThis.curve_bls12381 = curve;
    return curve;
}

// Si el proceso se vacía con la tarea a medias, avisa en vez de salir con éxito.
function run(task) {
    let finished = false;
    process.on("exit", (code) => {
        if (!finished && code === 0) {
            console.error("El proceso terminó antes de acabar. Vuelve a ejecutarlo.");
            process.exitCode = 1;
        }
    });
    task().then(() => {
        finished = true;
        process.exit(process.exitCode || 0);
    }, (err) => {
        finished = true;
        console.error(err.message || err);
        process.exit(1);
    });
}

module.exports = { useSingleThreadCurve, run };
