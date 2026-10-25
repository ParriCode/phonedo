pragma circom 2.1.6;

include "../node_modules/circomlib/circuits/bitify.circom";
include "../node_modules/circomlib/circuits/poseidon.circom";

// Compromiso Poseidon de un lote de N lecturas de 8 bits.
// Empaqueta 30 lecturas por elemento de campo y añade sesión y sal.
template BatchCommitment(N) {
    var PER_WORD = 30;
    var WORDS = (N + PER_WORD - 1) \ PER_WORD;

    signal input readings[N];
    signal input salt;
    signal input sessionId;
    signal output out;

    component bits[N];
    for (var i = 0; i < N; i++) {
        bits[i] = Num2Bits(8);
        bits[i].in <== readings[i];
    }

    signal acc[WORDS][PER_WORD + 1];
    for (var w = 0; w < WORDS; w++) {
        acc[w][0] <== 0;
        for (var j = 0; j < PER_WORD; j++) {
            var i = w * PER_WORD + j;
            if (i < N) {
                acc[w][j + 1] <== acc[w][j] + readings[i] * (256 ** j);
            } else {
                acc[w][j + 1] <== acc[w][j];
            }
        }
    }

    component hash = Poseidon(WORDS + 2);
    hash.inputs[0] <== sessionId;
    hash.inputs[1] <== salt;
    for (var w = 0; w < WORDS; w++) {
        hash.inputs[w + 2] <== acc[w][PER_WORD];
    }
    out <== hash.out;
}
