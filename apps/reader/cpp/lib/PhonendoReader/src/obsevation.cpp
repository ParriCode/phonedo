#include "observation.h"

#include <chrono>
#include <sstream>

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

std::string Observation::escapeJson(const std::string& value) {
    std::string escaped;
    for (char c : value) {
        switch (c) {
            case '"': escaped += "\\\""; break;
            case '\\': escaped += "\\\\"; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default: escaped += c; break;
        }
    }
    return escaped;
}

std::string Observation::toJson() const {
    std::ostringstream json;
    json << "{"
         << "\"observation_id\":\"" << escapeJson(observationId) << "\","
         << "\"observable_property\":\"" << escapeJson(observableProperty) << "\","
         << "\"simple_result\":\"" << escapeJson(simpleResult) << "\","
         << "\"phenomenon_time\":\"" << escapeJson(phenomenonTime) << "\","
         << "\"feature_of_interest\":\"" << escapeJson(featureOfInterest) << "\","
         << "\"procedure\":\"" << escapeJson(procedure) << "\","
         << "\"device_id\":\"" << escapeJson(deviceId) << "\","
         << "\"sensor_id\":\"" << escapeJson(sensorId) << "\","
         << "\"unit\":\"" << escapeJson(unit) << "\""
         << "}";
    return json.str();
}
