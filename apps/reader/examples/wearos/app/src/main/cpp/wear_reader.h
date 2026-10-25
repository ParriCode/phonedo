// Puente del Reader para Wear OS, sin JNI.
//
// Existe para que toda la lógica del Reader que usa la app (un ReaderCore con
// un dispositivo y un sensor de pulso, el ReaderService con su StreamOutput,
// el JSON de los endpoints y el sobre del evento) viva en C++ normal, que se
// compila y se prueba en el host con g++ (tests/native). reader_jni.cpp solo
// traduce tipos y serializa las llamadas con un mutex: esta clase, como la
// librería que envuelve, no es segura entre hilos.
//
// Orden de los miembros = orden de construcción: el sensor y el dispositivo
// viven más que el core (que guarda punteros a ellos) y el core más que el
// servicio, que se desengancha de su callback al destruirse.
#ifndef PHONENDO_WEAR_READER_H
#define PHONENDO_WEAR_READER_H

#include <cstddef>
#include <cstdint>
#include <string>

#include <core.h>
#include <reader_service.h>
#include <reader_stream.h>

class WearReader {
public:
    static constexpr const char* kDeviceId = "oneplus-watch-3";
    static constexpr const char* kSensorId = "heart-rate";

    explicit WearReader(const std::string& readerId, std::size_t queueSize = 64);
    WearReader(const WearReader&) = delete;
    WearReader& operator=(const WearReader&) = delete;

    // Publica un bpm en el stream. phenomenon_time sale de los milisegundos
    // epoch de la muestra. Si va bien, envelope es el sobre del evento, el
    // mismo JSON que reciben los suscriptores, listo para POST a /newEvent.
    bool ingestHeartRate(double bpm, std::int64_t epochMillis, std::string& envelope);

    std::string metadataJson() const;
    std::string devicesJson() const;
    bool deviceJson(const std::string& deviceId, std::string& out) const;

    SubscriberId subscribe();
    void unsubscribe(SubscriberId id);
    // Trama SSE lista para escribir: Event trae "event: observation", Closed y
    // Unknown traen "event: stream_closed"; Empty deja frame vacío.
    StreamPoll pollFrame(SubscriberId id, std::string& frame);
    std::size_t subscriberCount() const;
    void close();

    const std::string& readerId() const;
    const std::string& lastError() const;

private:
    ObservationStream stream;
    StreamOutput streamOutput;
    Sensor sensor;
    Device device;
    ReaderCore core;
    ReaderService service;
    std::string error;
};

#endif
