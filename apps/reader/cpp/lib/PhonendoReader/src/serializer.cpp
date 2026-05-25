/**
 * @file serializer.cpp
 * @author your name (you@domain.com)
 * @brief 
 * @version 0.1
 * @date 2026-05-25
 * 
 * @copyright Copyright (c) 2026
 * 
 */


#include "serializer.h"

static String slug(const String& value) {
    String result;
    result.reserve(value.length());

    bool previousDash = false;

    for (unsigned int i = 0; i < value.length(); i++) {
        char c = value[i];
        //undercase , convertirlo a minusculas
        if (c >= 'A' && c <= 'Z') {
            c += 32;
        }

        bool valid =
            (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') ||
            c == '_' ||
            c == '-';
        //Si el caracter no es válido se sutitye por -
        if (valid) {
            result += c;
            previousDash = false;
        } else if (!previousDash) {
            result += '-';
            previousDash = true;
        }
    }

    while (result.startsWith("-")) {
        result.remove(0, 1);
    }

    while (result.endsWith("-")) {
        result.remove(result.length() - 1);
    }

    if (result.length() == 0) {
        return "unknown";
    }

    return result;
}

static void appendRef(String& out, const char* prefix, const String& value) {
    out += F("ph:");
    out += prefix;
    out += '-';
    out += slug(value);
}

static void appendEscaped(String& out, const String& value) {
    for (unsigned int i = 0; i < value.length(); i++) {
        char c = value[i];

        switch (c) {
            case '\\':
                out += F("\\\\");
                break;
            case '"':
                out += F("\\\"");
                break;
            case '\n':
                out += F("\\n");
                break;
            case '\r':
                out += F("\\r");
                break;
            case '\t':
                out += F("\\t");
                break;
            default:
                out += c;
                break;
        }
    }
}

static void appendLiteral(String& out, const String& value) {
    out += '"';
    appendEscaped(out, value);
    out += '"';
}

static bool isIntegerValue(const String& value) {
    if (value.length() == 0) {
        return false;
    }

    unsigned int start = 0;

    if (value[0] == '-' || value[0] == '+') {
        start = 1;
    }

    if (start >= value.length()) {
        return false;
    }

    for (unsigned int i = start; i < value.length(); i++) {
        if (!isDigit(value[i])) {
            return false;
        }
    }

    return true;
}

static bool isDecimalValue(const String& value) {
    if (value.length() == 0) {
        return false;
    }

    bool hasDot = false;
    bool hasDigit = false;

    unsigned int start = 0;

    if (value[0] == '-' || value[0] == '+') {
        start = 1;
    }

    if (start >= value.length()) {
        return false;
    }

    for (unsigned int i = start; i < value.length(); i++) {
        char c = value[i];

        if (isDigit(c)) {
            hasDigit = true;
        } else if (c == '.' && !hasDot) {
            hasDot = true;
        } else {
            return false;
        }
    }

    return hasDigit && hasDot;
}

static void appendDateTimeLiteral(String& out, const String& value) {
    appendLiteral(out, value);
    out += F("^^xsd:dateTime");
}

static void appendDateTimeStampLiteral(String& out, const String& value) {
    appendLiteral(out, value);
    out += F("^^xsd:dateTimeStamp");
}

static void appendValueLiteral(String& out, const String& value) {
    if (value == "true" || value == "false") {
        appendLiteral(out, value);
        out += F("^^xsd:boolean");
        return;
    }

    if (isIntegerValue(value)) {
        appendLiteral(out, value);
        out += F("^^xsd:integer");
        return;
    }

    if (isDecimalValue(value)) {
        appendLiteral(out, value);
        out += F("^^xsd:decimal");
        return;
    }

    appendLiteral(out, value);
}

String serializeSosaTTL(const Observation& observation) {
    String ttl;
    ttl.reserve(900);

    String propertyName = observablePropertyToString(observation.observableProperty);
    String sensorName = observation.deviceId + "-" + propertyName;
    //F para que se guarde en memoría flash y no en la RAM consumiendo recursos limitados 
    //Es decir , este código coge de la memoería flash y le añade los parámetros para posteriormente si cargar el string necesario
    ttl += F("@prefix sosa: <http://www.w3.org/ns/sosa/> .\n");
    ttl += F("@prefix time: <http://www.w3.org/2006/time#> .\n");
    ttl += F("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n");
    ttl += F("@prefix ph: <urn:phonendo:> .\n\n");

    appendRef(ttl, "device", observation.deviceId);
    ttl += F(" a sosa:Platform .\n\n");

    appendRef(ttl, "sensor", sensorName);
    ttl += F("\n");
    ttl += F("    a sosa:Sensor ;\n");
    ttl += F("    sosa:isHostedBy ");
    appendRef(ttl, "device", observation.deviceId);
    ttl += F(" ;\n");
    ttl += F("    sosa:observes ");
    appendRef(ttl, "property", propertyName);
    ttl += F(" .\n\n");

    appendRef(ttl, "property", propertyName);
    ttl += F(" a sosa:ObservableProperty .\n");

    appendRef(ttl, "feature", observation.featureOfInterest);
    ttl += F(" a sosa:FeatureOfInterest .\n");

    appendRef(ttl, "procedure", observation.procedure);
    ttl += F(" a sosa:Procedure .\n\n");

    appendRef(ttl, "obs", observation.observationId);
    ttl += F("\n");
    ttl += F("    a sosa:Observation ;\n");

    ttl += F("    sosa:madeBySensor ");
    appendRef(ttl, "sensor", sensorName);
    ttl += F(" ;\n");

    ttl += F("    sosa:usedProcedure ");
    appendRef(ttl, "procedure", observation.procedure);
    ttl += F(" ;\n");

    ttl += F("    sosa:observedProperty ");
    appendRef(ttl, "property", propertyName);
    ttl += F(" ;\n");

    ttl += F("    sosa:hasFeatureOfInterest ");
    appendRef(ttl, "feature", observation.featureOfInterest);
    ttl += F(" ;\n");

    ttl += F("    sosa:resultTime ");
    appendDateTimeLiteral(ttl, observation.phenomenonTime);
    ttl += F(" ;\n");

    ttl += F("    sosa:phenomenonTime [\n");
    ttl += F("        a time:Instant ;\n");
    ttl += F("        time:inXSDDateTimeStamp ");
    appendDateTimeStampLiteral(ttl, observation.phenomenonTime);
    ttl += F("\n");
    ttl += F("    ] ;\n");

    ttl += F("    sosa:hasSimpleResult ");
    appendValueLiteral(ttl, observation.simpleResult);
    ttl += F(" .\n");

    return ttl;
}
