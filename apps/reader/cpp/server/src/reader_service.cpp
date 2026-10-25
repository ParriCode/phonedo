#include "reader_service.h"
#include "reader_serialization.h"
#include <utility>

ReaderService::ReaderService(ReaderCore& core, std::vector<ObservationOutput*> outputs)
    : outputs(std::move(outputs)), readerCore(core), attached(false) {
    if (readerCore.hasOnObservationCallback()) {
        lastError = "ReaderService requires a core without callbacks";
        return;
    }
    readerCore.setOnObservationCallback([this](const Observation& observation) {
        bool success = true;
        for (auto* output : this->outputs) {
            if (output && !output->publish(readerCore.getReaderId(), observation)) success = false;
        }
        return success;
    });
    attached = true;
}

ReaderService::~ReaderService() {
    // Solo se retira la callback propia.
    if (attached) readerCore.setOnObservationCallback(nullptr);
}

ReaderCore& ReaderService::core() {
    return readerCore;
}

bool ReaderService::ingest(const Observation& observation) {
    if (!attached) return false;
    return readerCore.ingest(observation);
}

bool ReaderService::isAttached() const {
    return attached;
}

const std::string& ReaderService::getLastError() const {
    return lastError;
}

std::string ReaderService::metadataJson(bool streamEnabled) const {
    return "{\"readerId\":" + jsonString(readerCore.getReaderId())
        + ",\"capabilities\":{\"stream\":" + (streamEnabled ? "true" : "false")
        + "},\"payloadFormats\":[\"application/json\"]}";
}

static std::string sensorsJson(Device& device) {
    std::string json = "[";
    for (std::uint8_t i = 0; i < device.sensorCount(); i++) {
        Sensor* sensor = device.sensorAt(i);
        if (sensor == nullptr) continue;
        if (json.size() > 1) json += ",";
        json += jsonString(sensor->sensorId);
    }
    return json + "]";
}

std::string ReaderService::devicesJson() const {
    // deviceAt no es const en el core; aquí solo se lee.
    std::string json = "[";
    for (std::uint8_t i = 0; i < readerCore.deviceCount(); i++) {
        Device* device = readerCore.deviceAt(i);
        if (device == nullptr) continue;
        if (json.size() > 1) json += ",";
        json += "{\"deviceId\":" + jsonString(device->deviceId)
            + ",\"deviceType\":" + jsonString(device->deviceType)
            + ",\"sensors\":" + sensorsJson(*device) + "}";
    }
    return json + "]";
}

bool ReaderService::deviceJson(const std::string& deviceId, std::string& out) const {
    if (!readerCore.hasDevice(deviceId)) return false;
    Device* device = readerCore.getDevice(deviceId);
    if (device == nullptr) return false;
    out = "{\"schemaVersion\":\"phonendo.device.v1\",\"readerId\":" + jsonString(readerCore.getReaderId())
        + ",\"deviceId\":" + jsonString(device->deviceId)
        + ",\"deviceType\":" + jsonString(device->deviceType)
        + ",\"creationDatetime\":" + jsonStringOrNull(device->creationDatetime)
        + ",\"sensors\":" + sensorsJson(*device) + "}";
    return true;
}
