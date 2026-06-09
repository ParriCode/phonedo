#ifndef PHONENDO_READER_CORE_H
#define PHONENDO_READER_CORE_H

#include <cstdint>
#include <string>

#include "device.h"
#include "observation.h"

#ifndef PHONENDO_MAX_DEVICES
#define PHONENDO_MAX_DEVICES 16
#endif

struct ReaderPolicy {
    bool allowNewDevices = true;
    bool allowNewSensors = true;
};

class ReaderCore {
public:
    ReaderCore(
        const std::string& readerId = "",
        ReaderPolicy policy = ReaderPolicy(),
        void (*on_register(std::string&, Device& )) = nullptr,
        void (*on_measurement(std::string&, Device& )) = nullptr
    );

    ~ReaderCore();

    std::string readerId;
    ReaderPolicy policy;
    std::string lastError;

    void (*onRegister)(std::string&, Device& );
    void (*onMeasurement)(std::string&, Device& );

    bool registerDevice(Device& device);
    bool addDevice(Device& device);
    bool removeDevice(const std::string& deviceId);

    Device* getDevice(const std::string& deviceId);
    bool hasDevice(const std::string& deviceId) const;

    std::uint8_t deviceCount() const;
    Device* deviceAt(std::uint8_t index);

    bool ingestRawMeasurement(
        const std::string& deviceId,
        const std::string& sensorId,
        const std::string& rawValue,
        const std::string& phenomenonTime = "",
        Observation* outputObservation = nullptr
    );

    bool handleMeasurementData(
        const Observation& measurement,
        Observation* outputObservation = nullptr
    );

private:
    Device* devices[PHONENDO_MAX_DEVICES];
    bool ownedDevices[PHONENDO_MAX_DEVICES];
    std::uint8_t devicesCount;

    Sensor* ownedSensors[PHONENDO_MAX_SENSORS];
    std::uint8_t ownedSensorsCount;

    bool addDevicePointer(Device* device, bool owned);

    static std::string generateReaderId();
};

#endif
