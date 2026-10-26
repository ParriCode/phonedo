# Librería nativa del Reader para Wear OS. Compila el núcleo y el servidor
# portables directamente desde apps/reader/cpp (no se copian: el ejemplo usa
# siempre la misma librería que el ESP32) más el puente y su capa JNI.
cmake_minimum_required(VERSION 3.22.1)
project(phonendo_reader_wearos CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# app/src/main/cpp -> apps/reader/cpp
get_filename_component(READER_CPP "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../../cpp" ABSOLUTE)

add_library(phonendo_reader SHARED
    ${READER_CPP}/core/src/core.cpp
    ${READER_CPP}/core/src/device.cpp
    ${READER_CPP}/core/src/observation.cpp
    ${READER_CPP}/core/src/sensor.cpp
    ${READER_CPP}/server/src/reader_service.cpp
    ${READER_CPP}/server/src/reader_stream.cpp
    ${READER_CPP}/server/src/serialization.cpp
    wear_reader.cpp
    reader_jni.cpp
)

target_include_directories(phonendo_reader PRIVATE
    ${READER_CPP}/core/include
    ${READER_CPP}/server/include
)

target_compile_options(phonendo_reader PRIVATE -Wall -Wextra)
target_link_libraries(phonendo_reader log)
