#ifndef PHONENDO_OBSERVATION_H
#define PHONENDO_OBSERVATION_H

#include <string>

class Observation {
public:
    Observation(
        const std::string& observableProperty = "",
        const std::string& simpleResult = "",
        const std::string& phenomenonTime = "",
        const std::string& featureOfInterest = "",
        const std::string& procedure = "",
        const std::string& deviceId = "",
        const std::string& sensorId = "",
        const std::string& unit = "",
        const std::string& observationId = ""
    );

    std::string observableProperty;
    std::string simpleResult;
    std::string phenomenonTime;
    std::string featureOfInterest;
    std::string procedure;
    std::string deviceId;
    std::string sensorId;
    std::string unit;
    std::string observationId;

    std::string toJson() const;

private:
    static std::string generateObservationId();
    static std::string escapeJson(const std::string& value);
};

#endif
