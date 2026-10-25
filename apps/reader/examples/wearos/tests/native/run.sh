#!/usr/bin/env bash
# Compila y ejecuta en el host la prueba del puente nativo (sin JNI), con los
# mismos fuentes de apps/reader/cpp que usa el CMakeLists.txt de la app.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_CPP="$HERE/../../app/src/main/cpp"
READER_CPP="$HERE/../../../../cpp"
OUT="$HERE/out"
mkdir -p "$OUT"

"${CXX:-g++}" -std=c++17 -Wall -Wextra -O1 \
    -I"$READER_CPP/core/include" -I"$READER_CPP/server/include" -I"$APP_CPP" \
    "$READER_CPP"/core/src/*.cpp "$READER_CPP"/server/src/*.cpp \
    "$APP_CPP/wear_reader.cpp" "$HERE/wear_reader_test.cpp" \
    -o "$OUT/wear_reader_test"

"$OUT/wear_reader_test"
