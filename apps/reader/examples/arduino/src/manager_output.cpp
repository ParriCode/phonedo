#include "manager_output.h"
#include "reader_serialization.h"

void ManagerOutput::registerDevice(const std::string&, const Device& device) {
    auto result = devices.insert(std::make_pair(device.deviceId, device));
    result.first->second = device;
    registered.erase(device.deviceId);
}

bool ManagerOutput::publish(const std::string& readerId, const Observation& observation) {
    if (registered.count(observation.deviceId) == 0) {
        auto device = devices.find(observation.deviceId);
        if (device == devices.end()) return false;
        if (!client.registerDevice(String(readerId.c_str()), device->second)) return false;
        registered.insert(observation.deviceId);
    }
    const std::string payload = observationToJson(observation);
    return client.sendObservationJSON(String(payload.c_str()), String(readerId.c_str()),
                                      String(observation.deviceId.c_str()));
}
