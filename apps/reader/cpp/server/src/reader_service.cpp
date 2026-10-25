#include "reader_service.h"
#include <utility>

ReaderService::ReaderService(ReaderCore& core, std::vector<ObservationOutput*> outputs)
    : outputs(std::move(outputs)), readerCore(core) {
    readerCore.setOnObservationCallback([this](const Observation& observation) {
        bool success = true;
        for (auto* output : this->outputs) {
            if (output && !output->publish(readerCore.getReaderId(), observation)) success = false;
        }
        return success;
    });
}

ReaderService::~ReaderService() {
    readerCore.setOnObservationCallback(nullptr);
}

ReaderCore& ReaderService::core() {
    return readerCore;
}

bool ReaderService::ingest(const Observation& observation) {
    return readerCore.ingest(observation);
}
