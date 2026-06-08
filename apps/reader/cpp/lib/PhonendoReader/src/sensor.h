#ifndef PHONENDO_SENSOR_H
#define PHONENDO_SENSOR_H

#include "observation.h"

class Sensor {
public:
    Sensor(
        const String& observableProperty,
        const String& procedure,
        const String& featureOfInterest,
        const String& sensorId = "",
        const String& unit = "",
        const String& deviceId = ""
    );

    String sensorId;
    String observableProperty;
    String procedure;
    String featureOfInterest;
    String unit;
    String deviceId;

    Observation buildObservation(
        const String& rawValue,
        const String& phenomenonTime = ""
    ) const;

    Observation addObservation(
        const String& simpleResult,
        const String& phenomenonTime = ""
    ) const;

private:
    static String generateSensorId();
    static String defaultPhenomenonTime();
};

#endif
