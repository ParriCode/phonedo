#include "manager_output.h"
#include "reader_serialization.h"

bool ManagerOutput::publish(const std::string& readerId, const Observation& observation) {
    const std::string payload = observationToJson(observation);
    return client.sendObservationJSON(String(payload.c_str()), String(readerId.c_str()),
                                      String(observation.deviceId.c_str()));
}
