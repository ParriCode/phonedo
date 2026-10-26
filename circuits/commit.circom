pragma circom 2.1.6;

include "lib/commitment.circom";

// Solo calcula el compromiso; lo usa el Verifier antes de firmar el lote.
component main {public [sessionId]} = BatchCommitment(5);
