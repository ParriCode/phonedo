#include "sensor.h"

#include <chrono>

Sensor::Sensor(
    const std::string& observableProperty,
    const std::string& procedure,
    const std::string& featureOfInterest,
    const std::string& sensorId,
    const std::string& unit,
    const std::string& deviceId
)
    : sensorId(sensorId.empty() ? generateSensorId() : sensorId),
      observableProperty(observableProperty),
      procedure(procedure),
      featureOfInterest(featureOfInterest),
      unit(unit),
      deviceId(deviceId) {
}

Observation Sensor::buildObservation(
    const std::string& rawValue,
    const std::string& phenomenonTime
) const {
    return Observation(
        observableProperty,
        rawValue,
        phenomenonTime.empty() ? defaultPhenomenonTime() : phenomenonTime,
        featureOfInterest,
        procedure,
        deviceId,
        sensorId,
        unit
    );
}

Observation Sensor::addObservation(
    const std::string& simpleResult,
    const std::string& phenomenonTime
) const {
    return buildObservation(simpleResult, phenomenonTime);
}

std::string Sensor::generateSensorId() {
    static unsigned long counter = 0;
    return "sensor-" + std::to_string(++counter);
}

std::string Sensor::defaultPhenomenonTime() {
    auto now = std::chrono::system_clock::now().time_since_epoch();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
    return std::to_string(ms);
}
