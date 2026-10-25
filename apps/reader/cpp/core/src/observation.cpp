#include "observation.h"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>

Observation::Observation(
    const std::string& observableProperty,
    const std::string& simpleResult,
    const std::string& phenomenonTime,
    const std::string& featureOfInterest,
    const std::string& procedure,
    const std::string& deviceId,
    const std::string& sensorId,
    const std::string& unit,
    const std::string& observationId
)
    : observableProperty(observableProperty),
      simpleResult(simpleResult),
      phenomenonTime(phenomenonTime),
      featureOfInterest(featureOfInterest),
      procedure(procedure),
      deviceId(deviceId),
      sensorId(sensorId),
      unit(unit),
      observationId(observationId.empty() ? generateObservationId() : observationId) {
}

std::string Observation::generateObservationId() {
    static unsigned long counter = 0;
    auto now = std::chrono::system_clock::now().time_since_epoch();
    auto micros = std::chrono::duration_cast<std::chrono::microseconds>(now).count();
    return std::to_string(micros) + "-" + std::to_string(++counter);
}

void Observation::setText(const std::string& value) {
    simpleResult = value;
    resultType = ResultType::Text;
}

void Observation::setInteger(long long value) {
    simpleResult = std::to_string(value);
    resultType = ResultType::Number;
}

void Observation::setNumber(double value) {
    if (!std::isfinite(value)) {
        setNull();
        return;
    }
    // La representación más corta que vuelve al mismo double, como repr() en Python.
    char buffer[32];
    for (int precision = 1; precision <= 17; precision++) {
        std::snprintf(buffer, sizeof(buffer), "%.*g", precision, value);
        if (std::strtod(buffer, nullptr) == value) {
            break;
        }
    }
    simpleResult = buffer;
    resultType = ResultType::Number;
}

void Observation::setBoolean(bool value) {
    simpleResult = value ? "true" : "false";
    resultType = ResultType::Boolean;
}

void Observation::setNull() {
    simpleResult.clear();
    resultType = ResultType::Null;
}

void Observation::setRawJson(const std::string& json) {
    if (json.empty()) {
        setNull();
        return;
    }
    simpleResult = json;
    resultType = ResultType::RawJson;
}

static void appendDigits(std::string& out, long long value, int width) {
    std::string digits = std::to_string(value);
    if (static_cast<int>(digits.size()) < width) {
        out.append(width - digits.size(), '0');
    }
    out += digits;
}

std::string isoUtcFromEpochMicros(std::int64_t micros) {
    // División entera hacia abajo para que las horas anteriores a 1970 cuadren.
    const std::int64_t perDay = 86400000000LL;
    std::int64_t days = micros / perDay;
    std::int64_t rest = micros % perDay;
    if (rest < 0) {
        rest += perDay;
        days--;
    }

    // Días civiles desde epoch (algoritmo de Howard Hinnant), sin gmtime.
    days += 719468;
    const std::int64_t era = (days >= 0 ? days : days - 146096) / 146097;
    const std::int64_t dayOfEra = days - era * 146097;
    const std::int64_t yearOfEra = (dayOfEra - dayOfEra / 1460 + dayOfEra / 36524 - dayOfEra / 146096) / 365;
    const std::int64_t dayOfYear = dayOfEra - (365 * yearOfEra + yearOfEra / 4 - yearOfEra / 100);
    const std::int64_t monthIndex = (5 * dayOfYear + 2) / 153;
    const std::int64_t day = dayOfYear - (153 * monthIndex + 2) / 5 + 1;
    const std::int64_t month = monthIndex < 10 ? monthIndex + 3 : monthIndex - 9;
    const std::int64_t year = yearOfEra + era * 400 + (month <= 2 ? 1 : 0);

    const std::int64_t seconds = rest / 1000000;
    const std::int64_t fraction = rest % 1000000;

    std::string iso;
    appendDigits(iso, year, 4);
    iso += '-';
    appendDigits(iso, month, 2);
    iso += '-';
    appendDigits(iso, day, 2);
    iso += 'T';
    appendDigits(iso, seconds / 3600, 2);
    iso += ':';
    appendDigits(iso, (seconds / 60) % 60, 2);
    iso += ':';
    appendDigits(iso, seconds % 60, 2);
    if (fraction != 0) {
        iso += '.';
        appendDigits(iso, fraction, 6);
    }
    iso += "+00:00";
    return iso;
}

std::string isoUtcFromEpochMillis(std::int64_t millis) {
    return isoUtcFromEpochMicros(millis * 1000);
}

static bool isDigits(const std::string& text, std::size_t from) {
    if (from >= text.size()) {
        return false;
    }
    for (std::size_t i = from; i < text.size(); i++) {
        if (text[i] < '0' || text[i] > '9') {
            return false;
        }
    }
    return true;
}

std::string normalizePhenomenonTime(const std::string& phenomenonTime) {
    if (isDigits(phenomenonTime, phenomenonTime.size() > 0 && phenomenonTime[0] == '-' ? 1 : 0)) {
        return isoUtcFromEpochMillis(std::strtoll(phenomenonTime.c_str(), nullptr, 10));
    }

    // Solo se toca lo que parece una fecha ISO: "YYYY-MM-DDTHH:MM...".
    const std::size_t separator = phenomenonTime.find('T');
    if (separator != 10 || phenomenonTime[4] != '-' || phenomenonTime[7] != '-') {
        return phenomenonTime;
    }

    const char last = phenomenonTime.back();
    if (last == 'Z' || last == 'z') {
        return phenomenonTime.substr(0, phenomenonTime.size() - 1) + "+00:00";
    }
    if (phenomenonTime.find_first_of("+-", separator) != std::string::npos) {
        return phenomenonTime;
    }
    return phenomenonTime + "+00:00";
}
