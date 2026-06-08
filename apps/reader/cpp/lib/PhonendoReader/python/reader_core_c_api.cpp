#include "../src/core.h"
#include "../src/serializer.h"

#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>

struct CoreHandle {
    ReaderCore core;
    std::vector<std::unique_ptr<Device>> devices;
    std::vector<std::unique_ptr<Sensor>> sensors;

    CoreHandle(const std::string& readerId, ReaderPolicy policy)
        : core(readerId, policy) {
    }
};

static std::string valueOr(const char* value, const char* fallback = "") {
    return value == nullptr ? std::string(fallback) : std::string(value);
}

static char* copyOut(const std::string& value) {
    char* out = static_cast<char*>(std::malloc(value.size() + 1));
    if (out == nullptr) return nullptr;
    std::memcpy(out, value.c_str(), value.size() + 1);
    return out;
}

extern "C" {

CoreHandle* prc_create(const char* readerId, bool allowNewDevices, bool allowNewSensors) {
    ReaderPolicy policy;
    policy.allowNewDevices = allowNewDevices;
    policy.allowNewSensors = allowNewSensors;
    return new CoreHandle(valueOr(readerId), policy);
}

void prc_destroy(CoreHandle* handle) {
    delete handle;
}

const char* prc_last_error(CoreHandle* handle) {
    return handle == nullptr ? "core is null" : handle->core.lastError.c_str();
}

void prc_free(char* value) {
    std::free(value);
}

bool prc_add_device(CoreHandle* handle, const char* deviceId, const char* deviceType, const char* platform) {
    if (handle == nullptr) return false;
    auto device = std::make_unique<Device>(valueOr(deviceId), valueOr(deviceType, "device"), valueOr(platform));
    if (!handle->core.addDevice(*device)) {
        return false;
    }
    handle->devices.push_back(std::move(device));
    return true;
}

bool prc_add_sensor(CoreHandle* handle, const char* deviceId, const char* sensorId, const char* observableProperty, const char* procedure, const char* featureOfInterest, const char* unit) {
    if (handle == nullptr) return false;
    Device* device = handle->core.getDevice(valueOr(deviceId));
    if (device == nullptr) return false;
    auto sensor = std::make_unique<Sensor>(
        valueOr(observableProperty, "unknown"),
        valueOr(procedure, "configured-measurement"),
        valueOr(featureOfInterest, "unknown-feature"),
        valueOr(sensorId),
        valueOr(unit),
        valueOr(deviceId)
    );
    if (!device->addSensor(*sensor)) {
        handle->core.lastError = "could not add sensor: " + valueOr(sensorId);
        return false;
    }
    handle->sensors.push_back(std::move(sensor));
    return true;
}

bool prc_has_device(CoreHandle* handle, const char* deviceId) {
    return handle != nullptr && handle->core.hasDevice(valueOr(deviceId));
}

bool prc_device_has_sensor(CoreHandle* handle, const char* deviceId, const char* sensorId) {
    if (handle == nullptr) return false;
    Device* device = handle->core.getDevice(valueOr(deviceId));
    return device != nullptr && device->hasSensor(valueOr(sensorId));
}

int prc_device_count(CoreHandle* handle) {
    return handle == nullptr ? 0 : int(handle->core.deviceCount());
}

bool prc_handle_measurement(CoreHandle* handle, const char* deviceId, const char* sensorId, const char* observableProperty, const char* simpleResult, const char* phenomenonTime, const char* featureOfInterest, const char* procedure, const char* unit, char** outputJson) {
    if (handle == nullptr || outputJson == nullptr) return false;
    Observation measurement(
        valueOr(observableProperty),
        valueOr(simpleResult),
        valueOr(phenomenonTime),
        valueOr(featureOfInterest),
        valueOr(procedure),
        valueOr(deviceId),
        valueOr(sensorId),
        valueOr(unit)
    );
    Observation output;
    if (!handle->core.handleMeasurementData(measurement, &output)) {
        return false;
    }
    *outputJson = copyOut(output.toJson());
    return *outputJson != nullptr;
}

bool prc_serialize_sosa_ttl(const char* deviceId, const char* sensorId, const char* observableProperty, const char* simpleResult, const char* phenomenonTime, const char* featureOfInterest, const char* procedure, const char* unit, const char* observationId, char** outputTtl) {
    if (outputTtl == nullptr) return false;
    Observation observation(
        valueOr(observableProperty),
        valueOr(simpleResult),
        valueOr(phenomenonTime),
        valueOr(featureOfInterest),
        valueOr(procedure),
        valueOr(deviceId),
        valueOr(sensorId),
        valueOr(unit),
        valueOr(observationId)
    );
    *outputTtl = copyOut(serializeSosaTTL(observation));
    return *outputTtl != nullptr;
}

}
