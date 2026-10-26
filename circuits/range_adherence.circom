pragma circom 2.1.6;

include "node_modules/circomlib/circuits/comparators.circom";
include "lib/commitment.circom";

// Demuestra que al menos minCount de N lecturas privadas están en
// [minValue, maxValue] y publica el compromiso del lote firmado por el Verifier.
template RangeAdherence(N) {
    signal input readings[N];
    signal input salt;

    signal input minValue;
    signal input maxValue;
    signal input minCount;
    signal input sessionId;

    signal output commitment;

    component minBits = Num2Bits(8);
    minBits.in <== minValue;
    component maxBits = Num2Bits(8);
    maxBits.in <== maxValue;

    component commit = BatchCommitment(N);
    commit.salt <== salt;
    commit.sessionId <== sessionId;

    component ge[N];
    component le[N];
    signal inRange[N];
    signal count[N + 1];
    count[0] <== 0;
    for (var i = 0; i < N; i++) {
        commit.readings[i] <== readings[i];

        ge[i] = GreaterEqThan(8);
        ge[i].in[0] <== readings[i];
        ge[i].in[1] <== minValue;
        le[i] = LessEqThan(8);
        le[i].in[0] <== readings[i];
        le[i].in[1] <== maxValue;

        inRange[i] <== ge[i].out * le[i].out;
        count[i + 1] <== count[i] + inRange[i];
    }

    var COUNT_BITS = 16;
    component countBits = Num2Bits(COUNT_BITS);
    countBits.in <== minCount;
    component enough = GreaterEqThan(COUNT_BITS);
    enough.in[0] <== count[N];
    enough.in[1] <== minCount;
    enough.out === 1;

    commitment <== commit.out;
}

component main {public [minValue, maxValue, minCount, sessionId]} = RangeAdherence(5);
