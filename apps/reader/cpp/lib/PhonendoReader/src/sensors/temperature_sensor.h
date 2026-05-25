#ifndef PHONENDO_TEMPERATURE_SENSOR_H
#define PHONENDO_TEMPERATURE_SENSOR_H

#include "../sensor_base.h"

class TemperatureSensor : public PeriodicSensor {
public:
    TemperatureSensor(
        const String& featureOfInterest,
        unsigned long intervalSeconds,
        const String& sensorId = "",
        const String& procedure = "temperature-measurement",
        const String& unit = "CELSIUS",
        float minValue = -20.0f,
        float maxValue = 80.0f,
        RawSensorAdapter* rawAdapter = nullptr,
        const String& deviceId = ""
    );

    String unit;
    float minValue;
    float maxValue;

    Observation buildObservation(
        const String& rawValue,
        const String& phenomenonTime = ""
    ) override;

private:
    bool parseTemperature(
        const String& rawValue,
        float& outputValue
    ) const;

    bool isInRange(float value) const;
};

#endif