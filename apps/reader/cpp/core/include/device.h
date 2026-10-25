#ifndef PHONENDO_DEVICE_H
#define PHONENDO_DEVICE_H

#include <cstdint>
#include <string>

#include "sensor.h"

#ifndef PHONENDO_MAX_SENSORS
#define PHONENDO_MAX_SENSORS 16
#endif

class Device {
public:
    Device(
        const std::string& deviceId,
        const std::string& deviceType = "device",
        const std::string& platform = ""
    );

    std::string deviceId;
    std::string deviceType;
    std::string platform;
    // Opcional: ISO 8601; vacío se publica como null.
    std::string creationDatetime;

    bool isValid() const;

    bool addSensor(Sensor& sensor);
    Sensor* getSensor(const std::string& sensorId);
    bool removeSensor(const std::string& sensorId);

    bool hasSensor(const std::string& sensorId) const;
    std::uint8_t sensorCount() const;

    Sensor* sensorAt(std::uint8_t index);
    std::string toString() const;

private:
    Sensor* sensors[PHONENDO_MAX_SENSORS];
    std::uint8_t sensorsCount;
};

#endif
