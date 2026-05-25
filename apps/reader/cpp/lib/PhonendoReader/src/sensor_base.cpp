#include "sensor_base.h"

SensorBase::SensorBase(
    ObservableProperty observableProperty,
    const String& procedure,
    const String& featureOfInterest,
    const String& sensorId,
    RawSensorAdapter* rawAdapter,
    const String& deviceId
)
    : observableProperty(observableProperty),
      procedure(procedure),
      featureOfInterest(featureOfInterest),
      deviceId(deviceId),
      rawAdapter(rawAdapter) {

    if (sensorId.length() == 0) {
        this->sensorId = generateSensorId();
    } else {
        this->sensorId = sensorId;
    }
}

Observation SensorBase::addObservation(
    const String& simpleResult,
    const String& phenomenonTime
) const {
    String finalPhenomenonTime = phenomenonTime;

    if (finalPhenomenonTime.length() == 0) {
        finalPhenomenonTime = defaultPhenomenonTime();
    }

    return Observation(
        observableProperty,
        simpleResult,
        finalPhenomenonTime,
        featureOfInterest,
        procedure,
        deviceId,
        sensorId
    );
}

String SensorBase::generateSensorId() {
    String id = "sensor-";

    id += String(millis(), HEX);
    id += "-";
    id += String(micros(), HEX);
    id += "-";
    id += String(random(0xFFFF), HEX);

    return id;
}

String SensorBase::defaultPhenomenonTime() {
    return String(millis());
}

// ===========================
// EventDrivenSensor
// ===========================

EventDrivenSensor::EventDrivenSensor(
    const String& sensorId,
    ObservableProperty observableProperty,
    const String& procedure,
    const String& featureOfInterest,
    const String& eventName,
    RawSensorAdapter* rawAdapter,
    const String& deviceId
)
    : SensorBase(
          observableProperty,
          procedure,
          featureOfInterest,
          sensorId,
          rawAdapter,
          deviceId
      ),
      eventName(eventName) {
}

// En Python esto era handle_event(), aquí lo dejamos camelCase
Observation EventDrivenSensor::handleEvent(
    const String& payload,
    const String& phenomenonTime
) {
    return buildObservation(payload, phenomenonTime);
}

// ===========================
// PeriodicSensor
// ===========================

PeriodicSensor::PeriodicSensor(
    ObservableProperty observableProperty,
    const String& procedure,
    const String& featureOfInterest,
    unsigned long intervalSeconds,
    const String& sensorId,
    RawSensorAdapter* rawAdapter,
    const String& deviceId
)
    : SensorBase(
          observableProperty,
          procedure,
          featureOfInterest,
          sensorId,
          rawAdapter,
          deviceId
      ),
      intervalMs(intervalSeconds * 1000UL),
      lastPollMs(0),
      hasBeenPolled(false) {
}

bool PeriodicSensor::shouldPoll() const {
    if (!hasBeenPolled) {
        return true;
    }

    unsigned long now = millis();

    return now - lastPollMs >= intervalMs;
}

Observation PeriodicSensor::poll(const String& phenomenonTime) {
    if (rawAdapter == nullptr) {
        Serial.print("Sensor without raw adapter: ");
        Serial.println(sensorId);

        return addObservation("ERROR_NO_RAW_ADAPTER", phenomenonTime);
    }

    String rawValue = rawAdapter->readRawValue();

    Observation observation = buildObservation(rawValue, phenomenonTime);

    lastPollMs = millis();
    hasBeenPolled = true;

    return observation;
}