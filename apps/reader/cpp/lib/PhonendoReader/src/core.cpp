#include "core.h"

ReaderCore::ReaderCore(
    const String& readerId,
    const String& token,
    const String& managerUrl,
    ReaderConfig config
)
    : readerId(readerId),
      config(config),
      managerClient(),
      lastError(""),
      devicesCount(0) {

    for (uint8_t i = 0; i < PHONENDO_MAX_DEVICES; i++) {
        devices[i] = nullptr;
    }

    if (this->readerId.length() == 0) {
        this->readerId = generateReaderId();
    }

    String finalManagerUrl = managerUrl.length() > 0
        ? managerUrl
        : this->config.managerUrl;

    String finalToken = token.length() > 0
        ? token
        : this->config.managerToken;

    managerClient = ManagerClient(finalManagerUrl, finalToken);
}

String ReaderCore::generateReaderId() {
    String id = "reader-";
    id += String(millis(), HEX);
    id += "-";
    id += String(micros(), HEX);
    id += "-";
    id += String(random(0xFFFF), HEX);

    return id;
}

bool ReaderCore::addDevice(Device& device) {
    lastError = "";

    if (!device.isValid()) {
        lastError = "device is invalid";
        return false;
    }

    if (devicesCount >= PHONENDO_MAX_DEVICES) {
        lastError = "max devices reached";
        return false;
    }

    if (hasDevice(device.deviceId)) {
        lastError = "device already exists: " + device.deviceId;
        return false;
    }

    devices[devicesCount] = &device;
    devicesCount++;

    return true;
}

bool ReaderCore::registerDevice(Device& device) {
    lastError = "";

    if (!addDevice(device)) {
        return false;
    }

    if (!managerClient.registerDevice(readerId, device)) {
        lastError = managerClient.lastError;
        return false;
    }

    return true;
}

bool ReaderCore::removeDevice(const String& deviceId) {
    lastError = "";

    if (deviceId.length() == 0) {
        lastError = "deviceId is empty";
        return false;
    }

    for (uint8_t i = 0; i < devicesCount; i++) {
        if (devices[i] != nullptr && devices[i]->deviceId == deviceId) {
            for (uint8_t j = i; j < devicesCount - 1; j++) {
                devices[j] = devices[j + 1];
            }

            devices[devicesCount - 1] = nullptr;
            devicesCount--;

            return true;
        }
    }

    lastError = "device not found: " + deviceId;
    return false;
}

Device* ReaderCore::getDevice(const String& deviceId) {
    if (deviceId.length() == 0) {
        lastError = "deviceId is empty";
        return nullptr;
    }

    for (uint8_t i = 0; i < devicesCount; i++) {
        if (devices[i] != nullptr && devices[i]->deviceId == deviceId) {
            return devices[i];
        }
    }

    lastError = "device not found: " + deviceId;
    return nullptr;
}

bool ReaderCore::hasDevice(const String& deviceId) const {
    if (deviceId.length() == 0) {
        return false;
    }

    for (uint8_t i = 0; i < devicesCount; i++) {
        if (devices[i] != nullptr && devices[i]->deviceId == deviceId) {
            return true;
        }
    }

    return false;
}

uint8_t ReaderCore::deviceCount() const {
    return devicesCount;
}

Device* ReaderCore::deviceAt(uint8_t index) {
    if (index >= devicesCount) {
        return nullptr;
    }

    return devices[index];
}

bool ReaderCore::ingestRawMeasurement(
    const String& deviceId,
    const String& sensorId,
    const String& rawValue,
    const String& phenomenonTime,
    bool send,
    Observation* outputObservation
) {
    lastError = "";

    Device* device = getDevice(deviceId);

    if (device == nullptr) {
        return false;
    }

    SensorBase* sensor = device->getSensor(sensorId);

    if (sensor == nullptr) {
        lastError = "sensor not found: " + sensorId;
        return false;
    }

    Observation observation = sensor->buildObservation(
        rawValue,
        phenomenonTime
    );

    if (outputObservation != nullptr) {
        *outputObservation = observation;
    }

    if (send) {
        return sendObservation(observation);
    }

    return true;
}

bool ReaderCore::sendObservation(const Observation& observation) {
    lastError = "";

    if (observation.deviceId.length() == 0) {
        lastError = "observation.deviceId is empty";
        return false;
    }

    Device* device = getDevice(observation.deviceId);

    if (device == nullptr) {
        return false;
    }

    String ttl = serializeSosaTTL(observation);

    if (!managerClient.sendObservationTTL(
        ttl,
        readerId,
        observation.deviceId
    )) {
        lastError = managerClient.lastError;
        return false;
    }

    return true;
}