#ifndef PHONENDO_SENSOR_BASE_H
#define PHONENDO_SENSOR_BASE_H

#include <Arduino.h>
#include "observation.h"

class RawSensorAdapter {
public:
    virtual ~RawSensorAdapter() {}

    virtual String readRawValue() = 0;
};

class SensorBase {
public:
    SensorBase(
        ObservableProperty observableProperty,
        const String& procedure,
        const String& featureOfInterest,
        const String& sensorId = "",
        RawSensorAdapter* rawAdapter = nullptr,
        const String& deviceId = ""
    );

    virtual ~SensorBase() {}

    String sensorId;
    ObservableProperty observableProperty;
    String procedure;
    String featureOfInterest;
    String deviceId;

    Observation addObservation(
        const String& simpleResult,
        const String& phenomenonTime = ""
    ) const;

    virtual Observation buildObservation(
        const String& rawValue,
        const String& phenomenonTime = ""
    ) = 0;

protected:
    RawSensorAdapter* rawAdapter;

    static String generateSensorId();
    static String defaultPhenomenonTime();
};

class EventDrivenSensor : public SensorBase {
public:
    EventDrivenSensor(
        const String& sensorId,
        ObservableProperty observableProperty,
        const String& procedure,
        const String& featureOfInterest,
        const String& eventName,
        RawSensorAdapter* rawAdapter = nullptr,
        const String& deviceId = ""
    );

    String eventName;

    Observation handleEvent(
        const String& payload,
        const String& phenomenonTime = ""
    );
};

class PeriodicSensor : public SensorBase {
public:
    PeriodicSensor(
        ObservableProperty observableProperty,
        const String& procedure,
        const String& featureOfInterest,
        unsigned long intervalSeconds,
        const String& sensorId = "",
        RawSensorAdapter* rawAdapter = nullptr,
        const String& deviceId = ""
    );

    bool shouldPoll() const;

    Observation poll(const String& phenomenonTime = "");

protected:
    unsigned long intervalMs;
    unsigned long lastPollMs;
    bool hasBeenPolled;
};

#endif