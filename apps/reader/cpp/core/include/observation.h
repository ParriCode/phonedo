#ifndef PHONENDO_OBSERVATION_H
#define PHONENDO_OBSERVATION_H

#include <cstdint>
#include <string>

// Tipo JSON de simple_result. Python conserva el tipo nativo del valor; aquí
// simpleResult guarda su texto y resultType dice cómo serializarlo.
enum class ResultType {
    Text,
    Number,
    Boolean,
    Null,
    RawJson
};

class Observation {
public:
    Observation(
        const std::string& observableProperty = "",
        const std::string& simpleResult = "",
        const std::string& phenomenonTime = "",
        const std::string& featureOfInterest = "",
        const std::string& procedure = "",
        const std::string& deviceId = "",
        const std::string& sensorId = "",
        const std::string& unit = "",
        const std::string& observationId = ""
    );

    std::string observableProperty;
    std::string simpleResult;
    std::string phenomenonTime;
    std::string featureOfInterest;
    std::string procedure;
    std::string deviceId;
    std::string sensorId;
    std::string unit;
    std::string observationId;
    ResultType resultType = ResultType::Text;

    void setText(const std::string& value);
    void setInteger(long long value);
    // NaN e infinito no son JSON válido: se guardan como null.
    void setNumber(double value);
    void setBoolean(bool value);
    void setNull();
    // Fragmento JSON confiado, sin validar; vacío equivale a null.
    void setRawJson(const std::string& json);

private:
    static std::string generateObservationId();
};

// Hora ISO 8601 en UTC con el formato de datetime.isoformat() de Python:
// "YYYY-MM-DDTHH:MM:SS[.ffffff]+00:00".
std::string isoUtcFromEpochMillis(std::int64_t millis);
std::string isoUtcFromEpochMicros(std::int64_t micros);

// Normaliza phenomenonTime como observation_to_dict: una hora ISO sin zona
// pasa a UTC (+00:00), "Z" se escribe +00:00 y un número entero se toma como
// milisegundos desde epoch. Cualquier otro texto se devuelve tal cual.
std::string normalizePhenomenonTime(const std::string& phenomenonTime);

#endif
