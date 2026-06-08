#ifndef PHONENDO_SENSOR_H
#define PHONENDO_SENSOR_H

#include <string>

#include "observation.h"

class Sensor {
public:
    Sensor(
        const std::string& observableProperty,
        const std::string& procedure,
        const std::string& featureOfInterest,
        const std::string& sensorId = "",
        const std::string& unit = "",
        const std::string& deviceId = ""
    );

    std::string sensorId;
    std::string observableProperty;
    std::string procedure;
    std::string featureOfInterest;
    std::string unit;
    std::string deviceId;

    Observation buildObservation(
        const std::string& rawValue,
        const std::string& phenomenonTime = ""
    ) const;

    Observation addObservation(
        const std::string& simpleResult,
        const std::string& phenomenonTime = ""
    ) const;

private:
    static std::string generateSensorId();
    static std::string defaultPhenomenonTime();
};

#endif
