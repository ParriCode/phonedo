// Prueba en el host del puente nativo, sin JNI ni Android.
//
// Comprueba el contrato que Kotlin da por hecho: una ingesta produce el sobre
// del evento que se manda a /newEvent y la misma trama llega al stream; los
// JSON de /metadata, /devices y /devices/{id} salen del ReaderService.
// Sin framework: cada fallo imprime la expectativa y el código de salida es 1.
#include <cstdio>
#include <regex>
#include <string>

#include "wear_reader.h"

static int failures = 0;

static void expect(bool condition, const std::string& what, const std::string& actual = "") {
    if (condition) return;
    failures++;
    std::printf("FALLO: %s\n", what.c_str());
    if (!actual.empty()) std::printf("  obtenido: %s\n", actual.c_str());
}

static bool contains(const std::string& text, const std::string& part) {
    return text.find(part) != std::string::npos;
}

int main() {
    WearReader reader("reader-wearos-test");
    expect(reader.lastError().empty(), "el puente arranca sin error", reader.lastError());

    const SubscriberId id = reader.subscribe();
    expect(id != 0, "subscribe() da un id válido");
    expect(reader.subscriberCount() == 1, "un suscriptor activo");

    // 2026-10-25T13:00:01.250Z
    std::string envelope;
    const bool ok = reader.ingestHeartRate(72.5, 1792933201250LL, envelope);
    expect(ok, "la ingesta de un bpm funciona", reader.lastError());

    expect(contains(envelope, "\"eventType\":\"observation\""), "eventType observation", envelope);
    expect(contains(envelope, "\"readerId\":\"reader-wearos-test\""), "readerId del sobre", envelope);
    expect(contains(envelope, "\"deviceId\":\"oneplus-watch-3\""), "deviceId del sobre", envelope);
    expect(contains(envelope, "\"payloadFormat\":\"application/json\""), "payloadFormat", envelope);
    expect(contains(envelope, "\"unit\":\"bpm\""), "unit bpm", envelope);
    expect(contains(envelope, "\"sensor_id\":\"heart-rate\""), "sensor_id heart-rate", envelope);
    expect(contains(envelope, "\"procedure\":\"health-services-ppg\""), "procedure", envelope);
    expect(contains(envelope, "\"feature_of_interest\":\"oneplus-watch-3\""), "feature_of_interest", envelope);
    expect(std::regex_search(envelope, std::regex("\"simple_result\":72\\.5[,}]")),
           "simple_result numérico (sin comillas)", envelope);
    expect(std::regex_search(envelope, std::regex(
               "\"phenomenon_time\":\"2026-10-25T13:00:01\\.250000\\+00:00\"")),
           "phenomenon_time ISO en UTC desde epoch millis", envelope);
    expect(!envelope.empty() && envelope.back() == '}', "el sobre es un objeto JSON", envelope);

    std::string frame;
    expect(reader.pollFrame(id, frame) == StreamPoll::Event, "el evento llega al stream");
    expect(frame == "event: observation\ndata: " + envelope + "\n\n",
           "la trama SSE lleva el mismo sobre", frame);
    expect(reader.pollFrame(id, frame) == StreamPoll::Empty && frame.empty(), "cola vacía tras leer");

    // Un valor no finito no es JSON: se publica como null, como setNumber().
    expect(reader.ingestHeartRate(0.0 / 0.0, 1792933202000LL, envelope), "ingesta de NaN");
    expect(contains(envelope, "\"simple_result\":null"), "NaN se publica como null", envelope);

    const std::string metadata = reader.metadataJson();
    expect(contains(metadata, "\"stream\":true"), "metadata con stream habilitado", metadata);
    expect(contains(metadata, "\"readerId\":\"reader-wearos-test\""), "metadata con readerId", metadata);

    const std::string devices = reader.devicesJson();
    expect(contains(devices, "\"deviceId\":\"oneplus-watch-3\"") &&
               contains(devices, "\"deviceType\":\"smartwatch\"") &&
               contains(devices, "\"sensors\":[\"heart-rate\"]"),
           "devices lista el reloj y su sensor", devices);

    std::string device;
    expect(reader.deviceJson("oneplus-watch-3", device) &&
               contains(device, "\"schemaVersion\":\"phonendo.device.v1\""),
           "deviceJson del reloj", device);
    expect(!reader.deviceJson("no-existe", device), "deviceJson de un id desconocido falla");

    reader.close();
    expect(reader.pollFrame(id, frame) == StreamPoll::Closed && frame == "event: stream_closed\ndata: {}\n\n",
           "close() avisa con stream_closed", frame);

    if (failures == 0) std::printf("OK: puente nativo\n");
    return failures == 0 ? 0 : 1;
}
