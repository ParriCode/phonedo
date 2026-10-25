#include "device.h"

#include <sstream>

Device::Device(
    const std::string& deviceId,
    const std::string& deviceType,
    const std::string& platform
)
    : deviceId(deviceId),
      deviceType(deviceType),
      platform(platform),
      sensorsCount(0) {
    for (std::uint8_t i = 0; i < PHONENDO_MAX_SENSORS; i++) {
        sensors[i] = nullptr;
    }
}

bool Device::isValid() const {
    return !deviceId.empty();
}

bool Device::addSensor(Sensor& sensor) {
    if (!isValid() || sensor.sensorId.empty() || sensorsCount >= PHONENDO_MAX_SENSORS || hasSensor(sensor.sensorId)) {
        return false;
    }
    sensor.deviceId = deviceId;
    sensors[sensorsCount++] = &sensor;
    return true;
}

Sensor* Device::getSensor(const std::string& sensorId) {
    if (sensorId.empty()) {
        return nullptr;
    }
    for (std::uint8_t i = 0; i < sensorsCount; i++) {
        if (sensors[i] != nullptr && sensors[i]->sensorId == sensorId) {
            return sensors[i];
        }
    }
    return nullptr;
}

bool Device::removeSensor(const std::string& sensorId) {
    if (sensorId.empty()) {
        return false;
    }
    for (std::uint8_t i = 0; i < sensorsCount; i++) {
        if (sensors[i] != nullptr && sensors[i]->sensorId == sensorId) {
            for (std::uint8_t j = i; j < sensorsCount - 1; j++) {
                sensors[j] = sensors[j + 1];
            }
            sensors[--sensorsCount] = nullptr;
            return true;
        }
    }
    return false;
}

bool Device::hasSensor(const std::string& sensorId) const {
    if (sensorId.empty()) {
        return false;
    }
    for (std::uint8_t i = 0; i < sensorsCount; i++) {
        if (sensors[i] != nullptr && sensors[i]->sensorId == sensorId) {
            return true;
        }
    }
    return false;
}

std::uint8_t Device::sensorCount() const {
    return sensorsCount;
}

Sensor* Device::sensorAt(std::uint8_t index) {
    return index >= sensorsCount ? nullptr : sensors[index];
}

std::string Device::toString() const {
    std::ostringstream text;
    text << "Device(deviceId=" << deviceId << ", deviceType=" << deviceType << ", platform=" << platform << ", sensors=[";
    for (std::uint8_t i = 0; i < sensorsCount; i++) {
        if (i > 0) {
            text << ", ";
        }
        if (sensors[i] != nullptr) {
            text << sensors[i]->sensorId;
        }
    }
    text << "])";
    return text.str();
}
