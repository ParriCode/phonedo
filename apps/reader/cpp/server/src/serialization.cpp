#include "reader_serialization.h"
#include <sstream>

static std::string escapeJson(const std::string& value) {
    std::string escaped;
    for (char c : value) {
        switch (c) {
            case '"': escaped += "\\\""; break;
            case '\\': escaped += "\\\\"; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    const char* hex = "0123456789abcdef";
                    escaped += "\\u00";
                    escaped += hex[(static_cast<unsigned char>(c) >> 4) & 0xf];
                    escaped += hex[static_cast<unsigned char>(c) & 0xf];
                } else {
                    escaped += c;
                }
                break;
        }
    }
    return escaped;
}

std::string jsonString(const std::string& value) {
    return "\"" + escapeJson(value) + "\"";
}

std::string jsonStringOrNull(const std::string& value) {
    return value.empty() ? std::string("null") : jsonString(value);
}

static std::string simpleResultJson(const Observation& observation) {
    switch (observation.resultType) {
        case ResultType::Number:
        case ResultType::Boolean:
        case ResultType::RawJson:
            return observation.simpleResult.empty() ? std::string("null") : observation.simpleResult;
        case ResultType::Null:
            return "null";
        case ResultType::Text:
        default:
            return jsonString(observation.simpleResult);
    }
}

std::string observationToJson(const Observation& observation) {
    std::ostringstream json;
    json << "{"
         << "\"observation_id\":" << jsonString(observation.observationId) << ","
         << "\"observable_property\":" << jsonString(observation.observableProperty) << ","
         << "\"simple_result\":" << simpleResultJson(observation) << ","
         << "\"phenomenon_time\":" << jsonString(normalizePhenomenonTime(observation.phenomenonTime)) << ","
         << "\"feature_of_interest\":" << jsonString(observation.featureOfInterest) << ","
         << "\"procedure\":" << jsonString(observation.procedure) << ","
         << "\"device_id\":" << jsonString(observation.deviceId) << ","
         << "\"sensor_id\":" << jsonString(observation.sensorId) << ","
         << "\"unit\":" << jsonStringOrNull(observation.unit)
         << "}";
    return json.str();
}

std::string observationEventToJson(const std::string& readerId, const Observation& observation) {
    return "{\"eventType\":\"observation\",\"readerId\":" + jsonString(readerId)
        + ",\"deviceId\":" + jsonString(observation.deviceId)
        + ",\"payloadFormat\":\"application/json\",\"payload\":" + observationToJson(observation) + "}";
}
