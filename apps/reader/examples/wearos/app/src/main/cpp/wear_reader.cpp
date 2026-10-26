// Implementación del puente: el mismo papel que setup() y send() en el
// ejemplo ESP32, pero con un único sensor de pulso y sin red. El envío a los
// Managers lo hace Kotlin con el sobre que devuelve ingestHeartRate(), así que
// el servicio solo tiene la salida al stream.
#include "wear_reader.h"

#include <reader_serialization.h>

WearReader::WearReader(const std::string& readerId, std::size_t queueSize)
    : stream(queueSize),
      streamOutput(stream),
      // Sensor(observableProperty, procedure, featureOfInterest, sensorId, unit).
      // Como en el ESP32, el feature_of_interest es el propio dispositivo.
      sensor("heart-rate", "health-services-ppg", kDeviceId, kSensorId, "bpm"),
      device(kDeviceId, "smartwatch", "wearos"),
      core(readerId),
      service(core, {&streamOutput}) {
    if (!stream.isValid()) error = stream.getLastError();
    if (!service.isAttached()) error = service.getLastError();
    device.addSensor(sensor);
    if (!core.addDevice(device)) error = core.getLastError();
}

bool WearReader::ingestHeartRate(double bpm, std::int64_t epochMillis, std::string& envelope) {
    error.clear();
    Observation observation = sensor.buildObservation("", isoUtcFromEpochMillis(epochMillis));
    observation.setNumber(bpm);
    if (!service.ingest(observation)) {
        error = core.getLastError().empty() ? service.getLastError() : core.getLastError();
        if (error.empty()) error = "ingest failed";
        return false;
    }
    envelope = observationEventToJson(core.getReaderId(), observation);
    return true;
}

std::string WearReader::metadataJson() const {
    return service.metadataJson(true);
}

std::string WearReader::devicesJson() const {
    return service.devicesJson();
}

bool WearReader::deviceJson(const std::string& deviceId, std::string& out) const {
    return service.deviceJson(deviceId, out);
}

SubscriberId WearReader::subscribe() {
    return stream.subscribe();
}

void WearReader::unsubscribe(SubscriberId id) {
    stream.unsubscribe(id);
}

StreamPoll WearReader::pollFrame(SubscriberId id, std::string& frame) {
    frame.clear();
    std::string event;
    const StreamPoll result = stream.poll(id, event);
    if (result == StreamPoll::Event) {
        frame = sseObservation(event);
    } else if (result != StreamPoll::Empty) {
        frame = sseStreamClosed();
    }
    return result;
}

std::size_t WearReader::subscriberCount() const {
    return stream.subscriberCount();
}

void WearReader::close() {
    stream.close();
}

const std::string& WearReader::readerId() const {
    return core.getReaderId();
}

const std::string& WearReader::lastError() const {
    return error;
}
