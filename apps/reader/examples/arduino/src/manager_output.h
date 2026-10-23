#ifndef PHONENDO_ARDUINO_MANAGER_OUTPUT_H
#define PHONENDO_ARDUINO_MANAGER_OUTPUT_H

#include "reader_service.h"
#include "manager_client.h"
#include <map>
#include <set>

// Arduino-specific HTTP delivery and registration policy.
class ManagerOutput : public ObservationOutput {
public:
    explicit ManagerOutput(ManagerClient& client) : client(client) {}
    void registerDevice(const std::string& readerId, const Device& device) override;
    bool publish(const std::string& readerId, const Observation& observation) override;

private:
    ManagerClient& client;
    std::map<std::string, Device> devices;
    std::set<std::string> registered;
};
#endif
