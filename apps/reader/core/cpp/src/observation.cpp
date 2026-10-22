#include "observation.h"

#include <chrono>

Observation::Observation(
    const std::string& observableProperty,
    const std::string& simpleResult,
    const std::string& phenomenonTime,
    const std::string& featureOfInterest,
    const std::string& procedure,
    const std::string& deviceId,
    const std::string& sensorId,
    const std::string& unit,
    const std::string& observationId
)
    : observableProperty(observableProperty),
      simpleResult(simpleResult),
      phenomenonTime(phenomenonTime),
      featureOfInterest(featureOfInterest),
      procedure(procedure),
      deviceId(deviceId),
      sensorId(sensorId),
      unit(unit),
      observationId(observationId.empty() ? generateObservationId() : observationId) {
}

std::string Observation::generateObservationId() {
    static unsigned long counter = 0;
    auto now = std::chrono::system_clock::now().time_since_epoch();
    auto micros = std::chrono::duration_cast<std::chrono::microseconds>(now).count();
    return std::to_string(micros) + "-" + std::to_string(++counter);
}

