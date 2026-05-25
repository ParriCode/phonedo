
/**
* @author: Jose Luis Parrilla Fuentes
*/


#ifndef PHONENDO_OBSERVATION_H
#define PHONENDO_OBSERVATION_H

#include <Arduino.h>
#include <string>

enum class ObservableProperty {
    HeartRate,
    Temperature,
    SpO2,
    Unknown
};

String observablePropertyToString(ObservableProperty property);

class Observation{
    public: 
        Observation(
            ObservableProperty observableProperty,
            const String& simpleResult,
            const String& phenomenonTime,
            const String& featureOfInterest,
            const String& procedure,
            const String& deviceId = "",
            const String& sensorId = "",
            const String& observationId = ""
        );

        ObservableProperty observableProperty;
        String simpleResult;
        String phenomenonTime;
        String featureOfInterest;
        String procedure;

        String deviceId;
        String sensorId;
        String observationId;

        String toJson() const;

    private:
        static String generateObservationId();
        static String escapeJson(const String& value);
};


#endif 