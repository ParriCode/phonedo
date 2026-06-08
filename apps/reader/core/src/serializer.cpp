#include "serializer.h"

#include <cctype>
#include <sstream>

static std::string slug(const std::string& value) {
    std::string result;
    bool previousDash = false;
    for (char raw : value) {
        char c = static_cast<char>(std::tolower(static_cast<unsigned char>(raw)));
        bool valid = std::isalnum(static_cast<unsigned char>(c)) || c == '_' || c == '-';
        if (valid) {
            result += c;
            previousDash = false;
        } else if (!previousDash) {
            result += '-';
            previousDash = true;
        }
    }
    while (!result.empty() && result.front() == '-') result.erase(result.begin());
    while (!result.empty() && result.back() == '-') result.pop_back();
    return result.empty() ? "unknown" : result;
}

static std::string ph(const std::string& value) {
    return "ph:" + slug(value);
}

static std::string escaped(const std::string& value) {
    std::string out;
    for (char c : value) {
        switch (c) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: out += c; break;
        }
    }
    return out;
}

std::string serializeSosaTTL(const Observation& observation) {
    bool hasUnit = !observation.unit.empty() && observation.unit != "unknown" && observation.unit != "UNKNOWN";
    std::ostringstream ttl;
    ttl << "@prefix sosa: <http://www.w3.org/ns/sosa/> .\n"
        << "@prefix time: <http://www.w3.org/2006/time#> .\n"
        << "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        << "@prefix ph: <urn:phonendo:> .\n";
    if (hasUnit) {
        ttl << "@prefix qudt: <http://qudt.org/schema/qudt/> .\n"
            << "@prefix unit: <http://qudt.org/vocab/unit/> .\n";
    }
    ttl << "\n"
        << ph(observation.deviceId) << " a sosa:Platform .\n\n"
        << ph(observation.sensorId) << "\n"
        << "    a sosa:Sensor ;\n"
        << "    sosa:isHostedBy " << ph(observation.deviceId) << " ;\n"
        << "    sosa:observes " << ph(observation.observableProperty) << " .\n\n"
        << ph(observation.observableProperty) << " a sosa:ObservableProperty .\n"
        << ph(observation.featureOfInterest) << " a sosa:FeatureOfInterest .\n"
        << ph(observation.procedure) << " a sosa:Procedure .\n\n"
        << ph(observation.observationId) << "\n"
        << "    a sosa:Observation ;\n"
        << "    sosa:madeBySensor " << ph(observation.sensorId) << " ;\n"
        << "    sosa:usedProcedure " << ph(observation.procedure) << " ;\n"
        << "    sosa:observedProperty " << ph(observation.observableProperty) << " ;\n"
        << "    sosa:hasFeatureOfInterest " << ph(observation.featureOfInterest) << " ;\n"
        << "    sosa:resultTime \"" << escaped(observation.phenomenonTime) << "\"^^xsd:dateTime ;\n"
        << "    sosa:phenomenonTime [\n"
        << "        a time:Instant ;\n"
        << "        time:inXSDDateTimeStamp \"" << escaped(observation.phenomenonTime) << "\"^^xsd:dateTimeStamp\n"
        << "    ] ;\n";
    if (hasUnit) {
        ttl << "    sosa:hasResult [\n"
            << "        a qudt:QuantityValue ;\n"
            << "        qudt:value " << observation.simpleResult << " ;\n"
            << "        qudt:hasUnit unit:" << observation.unit << "\n"
            << "    ] .\n";
    } else {
        ttl << "    sosa:hasSimpleResult \"" << escaped(observation.simpleResult) << "\" .\n";
    }
    return ttl.str();
}
