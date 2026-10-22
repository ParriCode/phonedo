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

std::string observationToJson(const Observation& observation) {
    std::ostringstream json;
    json << "{"
         << "\"observation_id\":\"" << escapeJson(observation.observationId) << "\","
         << "\"observable_property\":\"" << escapeJson(observation.observableProperty) << "\","
         << "\"simple_result\":\"" << escapeJson(observation.simpleResult) << "\","
         << "\"phenomenon_time\":\"" << escapeJson(observation.phenomenonTime) << "\","
         << "\"feature_of_interest\":\"" << escapeJson(observation.featureOfInterest) << "\","
         << "\"procedure\":\"" << escapeJson(observation.procedure) << "\","
         << "\"device_id\":\"" << escapeJson(observation.deviceId) << "\","
         << "\"sensor_id\":\"" << escapeJson(observation.sensorId) << "\","
         << "\"unit\":\"" << escapeJson(observation.unit) << "\""
         << "}";
    return json.str();
}
