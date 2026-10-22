#ifndef PHONENDO_READER_SERIALIZATION_H
#define PHONENDO_READER_SERIALIZATION_H
#include "observation.h"
#include <string>
std::string observationToJson(const Observation& observation);
#endif
