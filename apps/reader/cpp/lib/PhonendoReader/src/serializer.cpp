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

static void appendRef(String& out, const String& value) {
    out += F("ph:");
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
    appendLiteral(out, value);
}

String serializeSosaTTL(const Observation& observation) {
    String ttl;
    ttl.reserve(1000);

    bool hasUnit = observation.unit.length() > 0 && !observation.unit.equalsIgnoreCase("unknown");
    ttl += F("@prefix sosa: <http://www.w3.org/ns/sosa/> .\n");
    ttl += F("@prefix time: <http://www.w3.org/2006/time#> .\n");
    ttl += F("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n");
    ttl += F("@prefix ph: <urn:phonendo:> .\n");
    if (hasUnit) {
        ttl += F("@prefix qudt: <http://qudt.org/schema/qudt/> .\n");
        ttl += F("@prefix unit: <http://qudt.org/vocab/unit/> .\n");
    }
    ttl += F("\n");

    appendRef(ttl, observation.deviceId);
    ttl += F(" a sosa:Platform .\n\n");

    appendRef(ttl, observation.sensorId);
    ttl += F("\n");
    ttl += F("    a sosa:Sensor ;\n");
    ttl += F("    sosa:isHostedBy ");
    appendRef(ttl, observation.deviceId);
    ttl += F(" ;\n");
    ttl += F("    sosa:observes ");
    appendRef(ttl, observation.observableProperty);
    ttl += F(" .\n\n");

    appendRef(ttl, observation.observableProperty);
    ttl += F(" a sosa:ObservableProperty .\n");

    appendRef(ttl, observation.featureOfInterest);
    ttl += F(" a sosa:FeatureOfInterest .\n");

    appendRef(ttl, observation.procedure);
    ttl += F(" a sosa:Procedure .\n\n");

    appendRef(ttl, observation.observationId);
    ttl += F("\n");
    ttl += F("    a sosa:Observation ;\n");

    ttl += F("    sosa:madeBySensor ");
    appendRef(ttl, observation.sensorId);
    ttl += F(" ;\n");

    ttl += F("    sosa:usedProcedure ");
    appendRef(ttl, observation.procedure);
    ttl += F(" ;\n");

    ttl += F("    sosa:observedProperty ");
    appendRef(ttl, observation.observableProperty);
    ttl += F(" ;\n");

    ttl += F("    sosa:hasFeatureOfInterest ");
    appendRef(ttl, observation.featureOfInterest);
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

    if (!hasUnit) {
        ttl += F("    sosa:hasSimpleResult ");
        appendValueLiteral(ttl, observation.simpleResult);
        ttl += F(" .\n");
    } else {
        ttl += F("    sosa:hasResult [\n");
        ttl += F("        a qudt:QuantityValue ;\n");
        ttl += F("        qudt:value ");
        ttl += observation.simpleResult;
        ttl += F(" ;\n");
        ttl += F("        qudt:hasUnit unit:");
        ttl += observation.unit;
        ttl += F("\n");
        ttl += F("    ] .\n");
    }

    return ttl;
}
