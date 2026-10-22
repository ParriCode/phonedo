#ifndef PHONENDO_CORE_H
#define PHONENDO_CORE_H

#include <cstdint>
#include <string>

#include "device.h"
#include "sensor.h"
#include "observation.h"

#ifndef PHONENDO_MAX_DEVICES
#define PHONENDO_MAX_DEVICES 16
#endif

#ifndef PHONENDO_MAX_SENSORS
#define PHONENDO_MAX_SENSORS 32
#endif




class ReaderCore {
public:
    using OnRegisterCallback = void (*)(Device& device);
    using OnObservationCallback = bool (*)(
        const Observation& observation
    );

    ReaderCore(
        const std::string& readerId = "",
        bool allowNewDevices = true,
        bool allowNewSensors = true,
        OnRegisterCallback onRegister = nullptr,
        OnObservationCallback onObservation = nullptr
    );

    ~ReaderCore();

    static std::string generateReaderId();

    bool addDevicePointer(Device* device, bool owned);

    bool registerDevice(Device& device);

    bool removeDevice(const std::string& deviceId);

    Device* getDevice(const std::string& deviceId);
    bool hasDevice(const std::string& deviceId) const;

    std::uint8_t deviceCount() const;
    Device* deviceAt(std::uint8_t index);

    bool createObservation(
        const std::string& deviceId,
        const std::string& sensorId,
        const std::string& rawValue,
        const std::string& phenomenonTime,
        Observation* outputObservation = nullptr
    );

    bool ingest(
        const Observation& measurement,
        Observation* outputObservation = nullptr
    );

    bool sendObservation(const Observation& observation);

    const std::string& getReaderId() const;
    const std::string& getLastError() const;

    void setOnRegisterCallback(OnRegisterCallback callback);
    void setOnObservationCallback(OnObservationCallback callback);

private:
    std::string readerId;
    bool allowNewDevices;
    bool allowNewSensors;
    std::string lastError;

    Device* devices[PHONENDO_MAX_DEVICES];
    bool ownedDevices[PHONENDO_MAX_DEVICES];
    std::uint8_t devicesCount;

    Sensor* ownedSensors[PHONENDO_MAX_SENSORS];
    std::uint8_t ownedSensorsCount;

    OnRegisterCallback onRegister;
    OnObservationCallback onObservation;

};

#endif
