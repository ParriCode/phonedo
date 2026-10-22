#include "core.h"

#include <chrono>

ReaderCore::ReaderCore(
    const std::string& readerId,
    bool allowNewDevices,
    bool allowNewSensors,
    OnRegisterCallback onRegister,
    OnObservationCallback onObservation
)
    : readerId(readerId.empty() ? generateReaderId() : readerId),
      allowNewDevices(allowNewDevices),
      allowNewSensors(allowNewSensors),
      lastError(""),
      devicesCount(0),
      ownedSensorsCount(0),
      onRegister(onRegister),
      onObservation(onObservation) {
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

bool ReaderCore::addDevice(Device& device) {
    return addDevicePointer(&device, false);
}

bool ReaderCore::registerDevice(Device& device) {
    lastError.clear();

    if (!addDevicePointer(&device, false)) {
        return false;
    }

    if (onRegister != nullptr) {
        onRegister(device);
    }

    return true;
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
    if (index >= devicesCount) {
        return nullptr;
    }

    return devices[index];
}

bool ReaderCore::createObservation(
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

    Observation observation = sensor->buildObservation(rawValue, phenomenonTime);

    if (outputObservation != nullptr) {
        *outputObservation = observation;
    }

    return true;
}

bool ReaderCore::ingest(
    const Observation& measurement,
    Observation* outputObservation
) {
    lastError.clear();

    if (measurement.deviceId.find_first_not_of(" \t\r\n") == std::string::npos ||
        measurement.sensorId.find_first_not_of(" \t\r\n") == std::string::npos) {
        lastError = "deviceId and sensorId are required";
        return false;
    }
    const std::string& deviceId = measurement.deviceId;
    const std::string& sensorId = measurement.sensorId;

    Device* device = getDevice(deviceId);

    if (device == nullptr) {
        if (!this->allowNewDevices) {
            lastError = "device not found: " + deviceId;
            return false;
        }

        Device* newDevice = new Device(deviceId, "device");

        if (!addDevicePointer(newDevice, true)) {
            delete newDevice;
            return false;
        }

        device = newDevice;

        if (onRegister != nullptr) {
            onRegister(*device);
        }
    }

    if (!device->hasSensor(sensorId)) {
        if (!this->allowNewSensors) {
            lastError = "sensor not found: " + sensorId;
            return false;
        }

        if (ownedSensorsCount >= PHONENDO_MAX_SENSORS) {
            lastError = "max dynamic sensors reached";
            return false;
        }

        Sensor* sensor = new Sensor(
            measurement.observableProperty,

            measurement.procedure,

            measurement.featureOfInterest,

            sensorId,
            measurement.unit,
            deviceId
        );

        if (!device->addSensor(*sensor)) {
            delete sensor;
            lastError = "could not add dynamic sensor: " + sensorId;
            return false;
        }

        ownedSensors[ownedSensorsCount] = sensor;
        ownedSensorsCount++;
    }

    if (outputObservation != nullptr) {
        *outputObservation = measurement;
    }
    return sendObservation(measurement);
}

bool ReaderCore::sendObservation(const Observation& observation) {
    lastError.clear();

    if (observation.deviceId.find_first_not_of(" \t\r\n") == std::string::npos ||
        observation.sensorId.find_first_not_of(" \t\r\n") == std::string::npos) {
        lastError = "deviceId and sensorId are required";
        return false;
    }

    if (getDevice(observation.deviceId) == nullptr) {
        return false;
    }

    if (onObservation == nullptr) {
        return true;
    }

    if (!onObservation(observation)) {
        lastError = "onObservation callback failed";
        return false;
    }

    return true;
}

const std::string& ReaderCore::getReaderId() const {
    return readerId;
}

const std::string& ReaderCore::getLastError() const {
    return lastError;
}

void ReaderCore::setOnRegisterCallback(OnRegisterCallback callback) {
    onRegister = callback;
}

void ReaderCore::setOnObservationCallback(OnObservationCallback callback) {
    onObservation = callback;
}
