#ifndef PHONENDO_ESP32_READER_HTTP_H
#define PHONENDO_ESP32_READER_HTTP_H

#include <WebServer.h>
#include <WiFiClient.h>
#include <string>
#include <vector>

#include "reader_service.h"
#include "reader_stream.h"

#ifndef PHONENDO_MAX_SSE_CLIENTS
#define PHONENDO_MAX_SSE_CLIENTS 4
#endif

// Servidor HTTP del Reader con el mismo contrato que server.py:
// /health, /metadata, /devices, /devices/{id} y /stream (SSE).
// WebServer es síncrono: /stream se queda con el WiFiClient y loop() vacía
// las colas de cada suscriptor con poll().
class ReaderHttp {
public:
    ReaderHttp(ReaderService& service, ObservationStream& stream,
               const std::string& token, uint16_t port = 80);

    void begin();
    void poll();
    // Avisa con stream_closed a todos los suscriptores y los suelta.
    void close();
    std::size_t clientCount() const;

private:
    struct SseClient {
        WiFiClient client;
        SubscriberId id;
        unsigned long lastWrite;
    };

    bool authorized();
    void sendJson(int status, const std::string& body);
    void handleHealth();
    void handleMetadata();
    void handleDevices();
    void handleStream();
    void handleOther();
    bool write(SseClient& sse, const std::string& chunk);
    void drainClients();

    ReaderService& service;
    ObservationStream& stream;
    std::string token;
    WebServer server;
    std::vector<SseClient> clients;
};

#endif
