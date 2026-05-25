/**
 * @file serializer.h
 * @author Jose Luis Parrilla Fuentes (jlpf0006@red.ujaen.es)
 * @brief 
 * @version 0.1
 * @date 2026-05-25
 * 
 * @copyright Copyright (c) 2026
 * 
 */

#ifndef PHONENDO_SOSA_TTL_SERIALIZER_H
#define PHONENDO_SOSA_TTL_SERIALIZER_H

#include <Arduino.h>
#include "observation.h"

String serializeSosaTTL(const Observation& observation);

#endif