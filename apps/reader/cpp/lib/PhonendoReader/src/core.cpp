#include "core.h"

ReaderCore::ReaderCore(
    const String& readerId,
    const String& token,
    const String& managerUrl,
    ReaderConfig config,
    bool allowNewDevices,
    bool allowNewSensors
)
    : readerId(readerId),
      config(config),
      managerClient(),
      allowNewDevices(allowNewDevices),
      allowNewSensors(allowNewSensors),
      lastError(""),
      devicesCount(0),
      ownedSensorsCount(0) {

    for (uint8_t i = 0; i < PHONENDO_MAX_DEVICES; i++) {
        devices[i] = nullptr;
        ownedDevices[i] = false;
    }

    for (uint8_t i = 0; i < PHONENDO_MAX_SENSORS; i++) {
        ownedSensors[i] = nullptr;
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

ReaderCore::~ReaderCore() {
    for (uint8_t i = 0; i < ownedSensorsCount; i++) {
        delete ownedSensors[i];
        ownedSensors[i] = nullptr;
    }

    for (uint8_t i = 0; i < devicesCount; i++) {
        if (ownedDevices[i]) {
            delete devices[i];
        }

        devices[i] = nullptr;
        ownedDevices[i] = false;
    }
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
    return addDevicePointer(&device, false);
}

bool ReaderCore::addDevicePointer(Device* device, bool owned) {
    lastError = "";

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
            Device* removedDevice = devices[i];
            bool removedDeviceIsOwned = ownedDevices[i];

            for (uint8_t j = i; j < devicesCount - 1; j++) {
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

    Sensor* sensor = device->getSensor(sensorId);

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

bool ReaderCore::handleMeasurementData(
    const Observation& measurement,
    bool send,
    Observation* outputObservation
) {
    lastError = "";

    String deviceId = measurement.deviceId.length() > 0
        ? measurement.deviceId
        : readerId;

    String sensorId = measurement.sensorId.length() > 0
        ? measurement.sensorId
        : "unknown-sensor";

    Device* device = getDevice(deviceId);

    if (device == nullptr) {
        if (!allowNewDevices) {
            lastError = "device not found: " + deviceId;
            return false;
        }

        Device* newDevice = new Device(deviceId, "device");

        if (!addDevicePointer(newDevice, true)) {
            delete newDevice;
            return false;
        }

        if (!managerClient.registerDevice(readerId, *newDevice)) {
            lastError = managerClient.lastError;
            return false;
        }

        device = newDevice;
    }

    if (!device->hasSensor(sensorId)) {
        if (!allowNewSensors) {
            lastError = "sensor not found: " + sensorId;
            return false;
        }

        if (ownedSensorsCount >= PHONENDO_MAX_SENSORS) {
            lastError = "max dynamic sensors reached";
            return false;
        }

        String procedure = measurement.procedure.length() > 0
            ? measurement.procedure
            : "unknown";

        String featureOfInterest = measurement.featureOfInterest.length() > 0
            ? measurement.featureOfInterest
            : "unknown";

        String observableProperty = measurement.observableProperty.length() > 0
            ? measurement.observableProperty
            : "unknown";

        Sensor* sensor = new Sensor(
            observableProperty,
            procedure,
            featureOfInterest,
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
        send,
        outputObservation
    );
}

bool ReaderCore::sendObservation(const Observation& observation) {
    lastError = "";

    if (observation.deviceId.length() == 0) {
        lastError = "observation.deviceId is empty";
        return false;
    }

    if (getDevice(observation.deviceId) == nullptr) {
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
