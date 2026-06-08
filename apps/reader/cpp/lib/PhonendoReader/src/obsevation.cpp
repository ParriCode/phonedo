
/**
* @author: Jose Luis Parrilla Fuentes
*/

#include "observation.h"

Observation::Observation(
    const String& observableProperty,
    const String& simpleResult,
    const String& phenomenonTime,
    const String& featureOfInterest,
    const String& procedure,
    const String& deviceId,
    const String& sensorId,
    const String& unit,
    const String& observationId
)
    : observableProperty(observableProperty),
      simpleResult(simpleResult),
      phenomenonTime(phenomenonTime),
      featureOfInterest(featureOfInterest),
      procedure(procedure),
      deviceId(deviceId),
      sensorId(sensorId),
      unit(unit) {

    if (observationId.length() == 0) {
        this->observationId = generateObservationId();
    } else {
        this->observationId = observationId;
    }
}

String Observation::generateObservationId() {
    String id = "";

    id += String(millis(), HEX);
    id += String(micros(), HEX);
    id += String(random(0xFFFF), HEX);
    id += String(random(0xFFFF), HEX);

    return id;
}

String Observation::escapeJson(const String& value) {
    String escaped = "";

    for (unsigned int i = 0; i < value.length(); i++) {
        char c = value.charAt(i);

        if (c == '"') {
            escaped += "\\\"";
        } else if (c == '\\') {
            escaped += "\\\\";
        } else if (c == '\n') {
            escaped += "\\n";
        } else if (c == '\r') {
            escaped += "\\r";
        } else if (c == '\t') {
            escaped += "\\t";
        } else {
            escaped += c;
        }
    }

    return escaped;
}

String Observation::toJson() const {
    String json = "{";

    json += "\"observation_id\":\"";
    json += escapeJson(observationId);
    json += "\",";

    json += "\"observable_property\":\"";
    json += escapeJson(observableProperty);
    json += "\",";

    json += "\"simple_result\":\"";
    json += escapeJson(simpleResult);
    json += "\",";

    json += "\"phenomenon_time\":\"";
    json += escapeJson(phenomenonTime);
    json += "\",";

    json += "\"feature_of_interest\":\"";
    json += escapeJson(featureOfInterest);
    json += "\",";

    json += "\"procedure\":\"";
    json += escapeJson(procedure);
    json += "\"";

    if (deviceId.length() > 0) {
        json += ",\"device_id\":\"";
        json += escapeJson(deviceId);
        json += "\"";
    }

    if (sensorId.length() > 0) {
        json += ",\"sensor_id\":\"";
        json += escapeJson(sensorId);
        json += "\"";
    }

    if (unit.length() > 0) {
        json += ",\"unit\":\"";
        json += escapeJson(unit);
        json += "\"";
    }

    json += "}";

    return json;
}
