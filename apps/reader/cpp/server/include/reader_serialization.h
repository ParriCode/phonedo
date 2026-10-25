#ifndef PHONENDO_READER_SERIALIZATION_H
#define PHONENDO_READER_SERIALIZATION_H
#include "observation.h"
#include <string>

// JSON escrito a mano para compilar en Arduino sin librerías externas.
// Mismo contenido que serialization.py, aunque sin espacios entre separadores.
std::string observationToJson(const Observation& observation);
// Sobre del evento: {"eventType":"observation","readerId","deviceId","payloadFormat","payload"}.
std::string observationEventToJson(const std::string& readerId, const Observation& observation);

// Cadena JSON entre comillas y escapada.
std::string jsonString(const std::string& value);
// Igual, pero null si está vacía (los Optional[str] de Python).
std::string jsonStringOrNull(const std::string& value);
#endif
