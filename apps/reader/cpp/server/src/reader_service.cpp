#include "reader_service.h"
#include <utility>

ReaderService::ReaderService(ReaderCore& core, std::vector<ObservationOutput*> outputs)
    : outputs(std::move(outputs)), readerCore(core) {
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

ReaderService::~ReaderService() {
    readerCore.setOnRegisterCallback(nullptr);
    readerCore.setOnObservationCallback(nullptr);
}

ReaderCore& ReaderService::core() {
    return readerCore;
}

bool ReaderService::ingest(const Observation& observation) {
    return readerCore.ingest(observation);
}
