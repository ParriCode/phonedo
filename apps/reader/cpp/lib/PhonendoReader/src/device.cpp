#include "device.h"

Device::Device(
    const String& deviceId,
    const String& deviceType,
    const String& macAddress,
    const String& platform
)
    : deviceId(deviceId),
      deviceType(deviceType),
      macAddress(macAddress),
      platform(platform),
      sensorsCount(0) {

    for (uint8_t i = 0; i < PHONENDO_MAX_SENSORS; i++) {
        sensors[i] = nullptr;
    }
}

bool Device::isValid() const {
    return deviceId.length() > 0 &&
           macAddress.length() > 0;
}

bool Device::addSensor(SensorBase& sensor) {
    if (!isValid()) {
        return false;
    }

    if (sensor.sensorId.length() == 0) {
        return false;
    }

    if (sensorsCount >= PHONENDO_MAX_SENSORS) {
        return false;
    }

    if (hasSensor(sensor.sensorId)) {
        return false;
    }

    sensor.deviceId = deviceId;

    sensors[sensorsCount] = &sensor;
    sensorsCount++;

    return true;
}

SensorBase* Device::getSensor(const String& sensorId) {
    if (sensorId.length() == 0) {
        return nullptr;
    }

    for (uint8_t i = 0; i < sensorsCount; i++) {
        if (sensors[i] != nullptr && sensors[i]->sensorId == sensorId) {
            return sensors[i];
        }
    }

    return nullptr;
}

bool Device::removeSensor(const String& sensorId) {
    if (sensorId.length() == 0) {
        return false;
    }

    for (uint8_t i = 0; i < sensorsCount; i++) {
        if (sensors[i] != nullptr && sensors[i]->sensorId == sensorId) {
            for (uint8_t j = i; j < sensorsCount - 1; j++) {
                sensors[j] = sensors[j + 1];
            }

            sensors[sensorsCount - 1] = nullptr;
            sensorsCount--;

            return true;
        }
    }

    return false;
}

bool Device::hasSensor(const String& sensorId) const {
    if (sensorId.length() == 0) {
        return false;
    }

    for (uint8_t i = 0; i < sensorsCount; i++) {
        if (sensors[i] != nullptr && sensors[i]->sensorId == sensorId) {
            return true;
        }
    }

    return false;
}

uint8_t Device::sensorCount() const {
    return sensorsCount;
}

SensorBase* Device::sensorAt(uint8_t index) {
    if (index >= sensorsCount) {
        return nullptr;
    }

    return sensors[index];
}

String Device::toString() const {
    String text;

    text.reserve(160);

    text += F("Device(");
    text += F("deviceId=");
    text += deviceId;
    text += F(", deviceType=");
    text += deviceType;
    text += F(", macAddress=");
    text += macAddress;
    text += F(", platform=");
    text += platform;
    text += F(", sensors=[");

    for (uint8_t i = 0; i < sensorsCount; i++) {
        if (i > 0) {
            text += F(", ");
        }

        if (sensors[i] != nullptr) {
            text += sensors[i]->sensorId;
        }
    }

    text += F("])");

    return text;
}
