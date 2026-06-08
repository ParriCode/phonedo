#include "sensor.h"

Sensor::Sensor(
    const String& observableProperty,
    const String& procedure,
    const String& featureOfInterest,
    const String& sensorId,
    const String& unit,
    const String& deviceId
) {
    this->sensorId = sensorId.length() > 0 ? sensorId : generateSensorId();
    this->observableProperty = observableProperty;
    this->procedure = procedure;
    this->featureOfInterest = featureOfInterest;
    this->unit = unit;
    this->deviceId = deviceId;
}

Observation Sensor::buildObservation(
    const String& rawValue,
    const String& phenomenonTime
) const {
    String finalPhenomenonTime = phenomenonTime.length() > 0
        ? phenomenonTime
        : defaultPhenomenonTime();

    return Observation(
        observableProperty,
        rawValue,
        finalPhenomenonTime,
        featureOfInterest,
        procedure,
        deviceId,
        sensorId,
        unit
    );
}

Observation Sensor::addObservation(
    const String& simpleResult,
    const String& phenomenonTime
) const {
    return buildObservation(simpleResult, phenomenonTime);
}

String Sensor::generateSensorId() {
    return "sensor-" + String(micros()) + "-" + String(random(100000, 999999));
}

String Sensor::defaultPhenomenonTime() {
    return String(millis());
}
