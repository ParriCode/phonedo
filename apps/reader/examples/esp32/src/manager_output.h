#ifndef PHONENDO_ESP32_MANAGER_OUTPUT_H
#define PHONENDO_ESP32_MANAGER_OUTPUT_H

#include <string>
#include <vector>

#include "reader_service.h"

// Envía el sobre del evento a <url>/newEvent de cada Manager, como
// manager_output.py: el token va en el cuerpo JSON. Un Manager caído se
// registra por Serial y no impide entregar a los demás.
class ManagerOutput : public ObservationOutput {
public:
    // urls separadas por comas; las vacías se ignoran.
    ManagerOutput(const std::string& urls, const std::string& token, unsigned long timeoutMs = 5000);
    bool publish(const std::string& readerId, const Observation& observation) override;
    std::size_t managerCount() const;

private:
    std::vector<std::string> urls;
    std::string token;
    unsigned long timeoutMs;
};

#endif
