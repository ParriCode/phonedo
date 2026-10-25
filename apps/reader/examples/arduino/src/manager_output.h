#ifndef PHONENDO_ARDUINO_MANAGER_OUTPUT_H
#define PHONENDO_ARDUINO_MANAGER_OUTPUT_H

#include "reader_service.h"
#include "manager_client.h"

// Arduino-specific HTTP observation delivery.
class ManagerOutput : public ObservationOutput {
public:
    explicit ManagerOutput(ManagerClient& client) : client(client) {}
    bool publish(const std::string& readerId, const Observation& observation) override;

private:
    ManagerClient& client;
};
#endif
