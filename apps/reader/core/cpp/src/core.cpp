#include "core.h"

#include <chrono>

ReaderCore::ReaderCore(
    const std::string& readerId,
    ReaderPolicy policy,
    void (*on_register(std::string&, Device& )), 
    void (*on_measurement(std::string&, Device& ))
)
    : readerId(readerId.empty() ? generateReaderId() : readerId),
      policy(policy),
      lastError(""),
      devicesCount(0),
      ownedSensorsCount(0) {
    for (std::uint8_t i = 0; i < PHONENDO_MAX_DEVICES; i++) {
        devices[i] = nullptr;
        ownedDevices[i] = false;
    }
    for (std::uint8_t i = 0; i < PHONENDO_MAX_SENSORS; i++) {
        ownedSensors[i] = nullptr;
    }
}

ReaderCore::~ReaderCore() {
    for (std::uint8_t i = 0; i < ownedSensorsCount; i++) {
        delete ownedSensors[i];
        ownedSensors[i] = nullptr;
    }
    for (std::uint8_t i = 0; i < devicesCount; i++) {
        if (ownedDevices[i]) {
            delete devices[i];
        }
        devices[i] = nullptr;
        ownedDevices[i] = false;
    }
}

std::string ReaderCore::generateReaderId() {
    auto now = std::chrono::system_clock::now().time_since_epoch();
    auto micros = std::chrono::duration_cast<std::chrono::microseconds>(now).count();
    return "reader-" + std::to_string(micros);
}

bool ReaderCore::addDevice(Device& device) {
    return addDevicePointer(&device, false);
}

bool ReaderCore::addDevicePointer(Device* device, bool owned) {
    lastError.clear();
    if (device == nullptr || !device->isValid()) {
        lastError = "device is invalid";
        return false;
    }
    if (devicesCount >= PHONENDO_MAX_DEVICES) {
        lastError = "max devices reached";
        return false;
    }
    if (hasDevice(device->deviceId)) {
        lastError = "device already exists: " + device->deviceId;
        return false;
    }
    devices[devicesCount] = device;
    ownedDevices[devicesCount] = owned;
    devicesCount++;
    return true;
}

bool ReaderCore::registerDevice(Device& device) {
    addDevice(device);
    if (onRegister != nullptr) {
        onRegister(readerId, device);
        return true;
    }else{
        lastError = "onRegister callback is not set";
        return false;
    }
}

bool ReaderCore::removeDevice(const std::string& deviceId) {
    lastError.clear();
    if (deviceId.empty()) {
        lastError = "deviceId is empty";
        return false;
    }
    for (std::uint8_t i = 0; i < devicesCount; i++) {
        if (devices[i] != nullptr && devices[i]->deviceId == deviceId) {
            Device* removedDevice = devices[i];
            bool removedDeviceIsOwned = ownedDevices[i];
            for (std::uint8_t j = i; j < devicesCount - 1; j++) {
                devices[j] = devices[j + 1];
                ownedDevices[j] = ownedDevices[j + 1];
            }
            devices[devicesCount - 1] = nullptr;
            ownedDevices[devicesCount - 1] = false;
            devicesCount--;
            if (removedDeviceIsOwned) {
                delete removedDevice;
            }
            return true;
        }
    }
    lastError = "device not found: " + deviceId;
    return false;
}

Device* ReaderCore::getDevice(const std::string& deviceId) {
    if (deviceId.empty()) {
        lastError = "deviceId is empty";
        return nullptr;
    }
    for (std::uint8_t i = 0; i < devicesCount; i++) {
        if (devices[i] != nullptr && devices[i]->deviceId == deviceId) {
            return devices[i];
        }
    }
    lastError = "device not found: " + deviceId;
    return nullptr;
}

bool ReaderCore::hasDevice(const std::string& deviceId) const {
    if (deviceId.empty()) {
        return false;
    }
    for (std::uint8_t i = 0; i < devicesCount; i++) {
        if (devices[i] != nullptr && devices[i]->deviceId == deviceId) {
            return true;
        }
    }
    return false;
}

std::uint8_t ReaderCore::deviceCount() const {
    return devicesCount;
}

Device* ReaderCore::deviceAt(std::uint8_t index) {
    return index >= devicesCount ? nullptr : devices[index];
}

bool ReaderCore::ingestRawMeasurement(
    const std::string& deviceId,
    const std::string& sensorId,
    const std::string& rawValue,
    const std::string& phenomenonTime,
    Observation* outputObservation
) {
    lastError.clear();
    Device* device = getDevice(deviceId);
    if (device == nullptr) {
        return false;
    }
    Sensor* sensor = device->getSensor(sensorId);
    if (sensor == nullptr) {
        lastError = "sensor not found: " + sensorId;
        return false;
    }
    if (outputObservation != nullptr) {
        *outputObservation = sensor->buildObservation(rawValue, phenomenonTime);
    }
    return true;
}

bool ReaderCore::handleMeasurementData(
    const Observation& measurement,
    Observation* outputObservation
) {
    lastError.clear();
    std::string deviceId = measurement.deviceId.empty() ? readerId : measurement.deviceId;
    std::string sensorId = measurement.sensorId.empty() ? "unknown-sensor" : measurement.sensorId;

    Device* device = getDevice(deviceId);
    if (device == nullptr) {
        if (!policy.allowNewDevices) {
            lastError = "device not found: " + deviceId;
            return false;
        }
        Device* newDevice = new Device(deviceId, "device");
        if (!addDevicePointer(newDevice, true)) {
            delete newDevice;
            return false;
        }
        device = newDevice;
    }

    if (!device->hasSensor(sensorId)) {
        if (!policy.allowNewSensors) {
            lastError = "sensor not found: " + sensorId;
            return false;
        }
        if (ownedSensorsCount >= PHONENDO_MAX_SENSORS) {
            lastError = "max dynamic sensors reached";
            return false;
        }
        Sensor* sensor = new Sensor(
            measurement.observableProperty.empty() ? "unknown" : measurement.observableProperty,
            measurement.procedure.empty() ? "unknown" : measurement.procedure,
            measurement.featureOfInterest.empty() ? "unknown" : measurement.featureOfInterest,
            sensorId,
            measurement.unit,
            deviceId
        );
        if (!device->addSensor(*sensor)) {
            delete sensor;
            lastError = "could not add dynamic sensor: " + sensorId;
            return false;
        }
        ownedSensors[ownedSensorsCount++] = sensor;
    }

    return ingestRawMeasurement(
        deviceId,
        sensorId,
        measurement.simpleResult,
        measurement.phenomenonTime,
        outputObservation
    );
}
