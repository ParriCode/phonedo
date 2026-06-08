#ifndef PHONENDO_READER_CORE_H
#define PHONENDO_READER_CORE_H

#include <Arduino.h>

#include "device.h"
#include "observation.h"
#include "manager_client.h"
#include "serializer.h"

#ifndef PHONENDO_MAX_DEVICES
#define PHONENDO_MAX_DEVICES 4
#endif

struct ReaderConfig {
    bool enableBluetooth = true;
    bool enableHttp = true;
    bool enableLocal = true;
    String managerUrl = "";
    String managerToken = "";
};

class ReaderCore {
public:
    ReaderCore(
        const String& readerId = "",
        const String& token = "",
        const String& managerUrl = "",
        ReaderConfig config = ReaderConfig(),
        bool allowNewDevices = true,
        bool allowNewSensors = true
    );

    ~ReaderCore();

    String readerId;
    ReaderConfig config;
    ManagerClient managerClient;
    bool allowNewDevices;
    bool allowNewSensors;

    String lastError;

    bool registerDevice(Device& device);
    bool addDevice(Device& device);
    bool removeDevice(const String& deviceId);

    Device* getDevice(const String& deviceId);
    bool hasDevice(const String& deviceId) const;

    uint8_t deviceCount() const;
    Device* deviceAt(uint8_t index);

    bool ingestRawMeasurement(
        const String& deviceId,
        const String& sensorId,
        const String& rawValue,
        const String& phenomenonTime = "",
        bool send = true,
        Observation* outputObservation = nullptr
    );

    bool handleMeasurementData(
        const Observation& measurement,
        bool send = true,
        Observation* outputObservation = nullptr
    );

    bool sendObservation(const Observation& observation);

private:
    Device* devices[PHONENDO_MAX_DEVICES];
    bool ownedDevices[PHONENDO_MAX_DEVICES];
    uint8_t devicesCount;

    Sensor* ownedSensors[PHONENDO_MAX_SENSORS];
    uint8_t ownedSensorsCount;

    bool addDevicePointer(Device* device, bool owned);

    static String generateReaderId();
};

#endif
