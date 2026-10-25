#ifndef PHONENDO_READER_SERVICE_H
#define PHONENDO_READER_SERVICE_H

#include "core.h"
#include <vector>

// Platform adapters implement this port. Asynchronous outputs must copy observations.
class ObservationOutput {
public:
    virtual ~ObservationOutput() = default;
    virtual bool publish(const std::string& readerId, const Observation& observation) = 0;
};

// Borrows a core and exclusively manages its callbacks.
// Core and outputs must outlive the service; do not replace callbacks while attached.
// Como en Python, no pisa una callback previa: queda sin enganchar (isAttached()
// falso, getLastError() lo explica) e ingest() devuelve false.
class ReaderService {
public:
    ReaderService(ReaderCore& core, std::vector<ObservationOutput*> outputs = {});
    ~ReaderService();
    ReaderService(const ReaderService&) = delete;
    ReaderService& operator=(const ReaderService&) = delete;

    ReaderCore& core();
    bool ingest(const Observation& observation);
    bool isAttached() const;
    const std::string& getLastError() const;

    // Cuerpos JSON de /metadata, /devices y /devices/{id}, como service.py.
    std::string metadataJson(bool streamEnabled = false) const;
    std::string devicesJson() const;
    // false si el dispositivo no existe; entonces out no se modifica.
    bool deviceJson(const std::string& deviceId, std::string& out) const;

private:
    std::vector<ObservationOutput*> outputs;
    ReaderCore& readerCore;
    bool attached;
    std::string lastError;
};

// Embedded transports implement their own listening loop; no network API is required here.
class ReaderServer {
public:
    virtual ~ReaderServer() = default;
    virtual bool start() = 0;
    virtual void poll() = 0;
    virtual void stop() = 0;
};

#endif
