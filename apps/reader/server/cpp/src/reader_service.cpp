#include "reader_service.h"
#include <utility>

ReaderService::ReaderService(const std::string& readerId,
                             std::vector<ObservationOutput*> outputs,
                             bool allowNewDevices, bool allowNewSensors)
    : outputs(std::move(outputs)),
      readerCore(readerId, allowNewDevices, allowNewSensors) {
    readerCore.setOnRegisterCallback([this](Device& device) {
        for (auto* output : this->outputs) {
            if (output) output->registerDevice(readerCore.getReaderId(), device);
        }
    });
    readerCore.setOnObservationCallback([this](const Observation& observation) {
        bool success = true;
        for (auto* output : this->outputs) {
            if (output && !output->publish(readerCore.getReaderId(), observation)) success = false;
        }
        return success;
    });
}

ReaderCore& ReaderService::core() {
    return readerCore;
}

bool ReaderService::ingest(const Observation& observation) {
    return readerCore.ingest(observation);
}
