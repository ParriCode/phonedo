#include "temperature_sensor.h"
#include <stdlib.h>

TemperatureSensor::TemperatureSensor(
    const String& featureOfInterest,
    unsigned long intervalSeconds,
    const String& sensorId,
    const String& procedure,
    const String& unit,
    float minValue,
    float maxValue,
    RawSensorAdapter* rawAdapter,
    const String& deviceId
)
    : PeriodicSensor(
          ObservableProperty::Temperature,
          procedure,
          featureOfInterest,
          intervalSeconds,
          sensorId,
          rawAdapter,
          deviceId
      ),
      unit(unit),
      minValue(minValue),
      maxValue(maxValue) {
}

Observation TemperatureSensor::buildObservation(
    const String& rawValue,
    const String& phenomenonTime
) {
    float temperature = 0.0f;

    if (!parseTemperature(rawValue, temperature)) {
        return addObservation("ERROR_INVALID_TEMPERATURE", phenomenonTime);
    }

    if (!isInRange(temperature)) {
        return addObservation("ERROR_TEMPERATURE_OUT_OF_RANGE", phenomenonTime);
    }

    return addObservation(String(temperature, 2), phenomenonTime);
}

bool TemperatureSensor::parseTemperature(
    const String& rawValue,
    float& outputValue
) const {
    String cleanValue = rawValue;
    cleanValue.trim();

    if (cleanValue.length() == 0) {
        return false;
    }

    char* endPointer = nullptr;
    double parsedValue = strtod(cleanValue.c_str(), &endPointer);

    if (endPointer == cleanValue.c_str()) {
        return false;
    }

    if (*endPointer != '\0') {
        return false;
    }

    outputValue = static_cast<float>(parsedValue);
    return true;
}

bool TemperatureSensor::isInRange(float value) const {
    return value >= minValue && value <= maxValue;
}