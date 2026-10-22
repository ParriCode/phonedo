#include "core.h"

#ifdef ARDUINO
#include <Arduino.h>
#else
#include <chrono>
#endif

ReaderCore::ReaderCore(
    const std::string& readerId,
    bool allowNewDevices,
    bool allowNewSensors,
    OnRegisterCallback onRegister,
    OnSendCallback onSend
)
    : readerId(readerId.empty() ? generateReaderId() : readerId),
      allowNewDevices(allowNewDevices),
      allowNewSensors(allowNewSensors),
      lastError(""),
      devicesCount(0),
      ownedSensorsCount(0),
      onRegister(onRegister),
      onSend(onSend) {
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
#ifdef ARDUINO
    return "reader-" + std::to_string(millis());
#else
    auto now = std::chrono::system_clock::now().time_since_epoch();
    auto micros = std::chrono::duration_cast<std::chrono::microseconds>(now).count();
    return "reader-" + std::to_string(micros);
#endif
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
    lastError.clear();

    if (!addDevicePointer(&device, false)) {
        return false;
    }

    if (onRegister != nullptr) {
        onRegister(readerId, device);
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

    Observation observation = sensor->buildObservation(rawValue, phenomenonTime);

    if (outputObservation != nullptr) {
        *outputObservation = observation;
    }

    return sendObservation(observation);
}

bool ReaderCore::handleMeasurementData(
    const Observation& measurement,
    Observation* outputObservation
) {
    lastError.clear();

    std::string deviceId = measurement.deviceId.empty()
        ? readerId
        : measurement.deviceId;

    std::string sensorId = measurement.sensorId.empty()
        ? "unknown-sensor"
        : measurement.sensorId;

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
            onRegister(readerId, *device);
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
            measurement.observableProperty.empty()
                ? "unknown"
                : measurement.observableProperty,

            measurement.procedure.empty()
                ? "unknown"
                : measurement.procedure,

            measurement.featureOfInterest.empty()
                ? "unknown"
                : measurement.featureOfInterest,

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

    return ingestRawMeasurement(
        deviceId,
        sensorId,
        measurement.simpleResult,
        measurement.phenomenonTime,
        outputObservation
    );
}

bool ReaderCore::sendObservation(const Observation& observation) {
    lastError.clear();

    if (observation.deviceId.empty()) {
        lastError = "observation.deviceId is empty";
        return false;
    }

    if (getDevice(observation.deviceId) == nullptr) {
        return false;
    }

    if (onSend == nullptr) {
        lastError = "onSend callback is not set";
        return false;
    }

    std::string observation_payload = observation.toJson();

    if (!onSend(observation_payload, readerId, observation.deviceId)) {
        lastError = "onSend callback failed";
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

void ReaderCore::setOnSendCallback(OnSendCallback callback) {
    onSend = callback;
}
