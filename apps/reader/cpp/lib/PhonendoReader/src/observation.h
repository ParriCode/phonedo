
/**
* @author: Jose Luis Parrilla Fuentes
*/


#ifndef PHONENDO_OBSERVATION_H
#define PHONENDO_OBSERVATION_H

#include <Arduino.h>
class Observation{
    public: 
        Observation(
            const String& observableProperty,
            const String& simpleResult,
            const String& phenomenonTime,
            const String& featureOfInterest,
            const String& procedure,
            const String& deviceId = "",
            const String& sensorId = "",
            const String& unit = "",
            const String& observationId = ""
        );

        String observableProperty;
        String simpleResult;
        String phenomenonTime;
        String featureOfInterest;
        String procedure;

        String deviceId;
        String sensorId;
        String unit;
        String observationId;

        String toJson() const;

    private:
        static String generateObservationId();
        static String escapeJson(const String& value);
};


#endif 
