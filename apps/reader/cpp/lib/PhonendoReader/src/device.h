/**
 * @file device.h
 * @author your name (you@domain.com)
 * @brief 
 * @version 0.1
 * @date 2026-05-25
 * 
 * @copyright Copyright (c) 2026
 * 
 */

 #ifndef PHONENDO_DEVICE_H
#define PHONENDO_DEVICE_H

#include <Arduino.h>
#include "sensor_base.h"

#ifndef PHONENDO_MAX_SENSORS
#define PHONENDO_MAX_SENSORS 8
#endif

class Device {
public:
    Device(
        const String& deviceId,
        const String& deviceType,
        const String& macAddress,
        const String& platform = ""
    );

    String deviceId;
    String deviceType;
    String macAddress;
    String platform;

    bool isValid() const;

    bool addSensor(SensorBase& sensor);
    SensorBase* getSensor(const String& sensorId);
    bool removeSensor(const String& sensorId);

    bool hasSensor(const String& sensorId) const;
    uint8_t sensorCount() const;

    SensorBase* sensorAt(uint8_t index);

    String toString() const;

private:
    SensorBase* sensors[PHONENDO_MAX_SENSORS];
    uint8_t sensorsCount;
};

#endif
