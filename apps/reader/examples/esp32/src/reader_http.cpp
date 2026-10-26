#include "reader_http.h"

#include <Arduino.h>

#include "reader_serialization.h"

ReaderHttp::ReaderHttp(ReaderService& service, ObservationStream& stream,
                       const std::string& token, uint16_t port)
    : service(service), stream(stream), token(token), server(port) {
}

void ReaderHttp::begin() {
    // WebServer solo guarda las cabeceras que se le piden.
    static const char* headers[] = {"Authorization"};
    server.collectHeaders(headers, 1);
    server.on("/health", HTTP_GET, [this]() { handleHealth(); });
    server.on("/metadata", HTTP_GET, [this]() { handleMetadata(); });
    server.on("/devices", HTTP_GET, [this]() { handleDevices(); });
    server.on("/stream", HTTP_GET, [this]() { handleStream(); });
    // /devices/{id} y las rutas desconocidas.
    server.onNotFound([this]() { handleOther(); });
    server.begin();
}

void ReaderHttp::poll() {
    server.handleClient();
    drainClients();
}

std::size_t ReaderHttp::clientCount() const {
    return clients.size();
}

bool ReaderHttp::authorized() {
    if (token.empty()) return true;
    const std::string expected = "Bearer " + token;
    const String received = server.header("Authorization");
    // Comparación en tiempo constante respecto al contenido, como hmac.compare_digest.
    unsigned char diff = received.length() == expected.size() ? 0 : 1;
    for (std::size_t i = 0; i < expected.size(); i++) {
        const char c = i < received.length() ? received[i] : 0;
        diff |= static_cast<unsigned char>(c ^ expected[i]);
    }
    if (diff == 0) return true;
    sendJson(401, "{\"error\":\"unauthorized\"}");
    return false;
}

void ReaderHttp::sendJson(int status, const std::string& body) {
    // CORS abierto: permite que un panel HTML en el navegador lea el Reader.
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(status, "application/json", body.c_str());
}

void ReaderHttp::handleHealth() {
    if (authorized()) sendJson(200, "{\"status\":\"ok\"}");
}

void ReaderHttp::handleMetadata() {
    if (authorized()) sendJson(200, service.metadataJson(true));
}

void ReaderHttp::handleDevices() {
    if (authorized()) sendJson(200, service.devicesJson());
}

void ReaderHttp::handleOther() {
    // Preflight del navegador (lo dispara la cabecera Authorization); no lleva token.
    if (server.method() == HTTP_OPTIONS) {
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.sendHeader("Access-Control-Allow-Headers", "Authorization");
        server.sendHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
        server.send(204);
        return;
    }
    if (!authorized()) return;
    const std::string uri = server.uri().c_str();
    const std::string prefix = "/devices/";
    if (server.method() == HTTP_GET && uri.rfind(prefix, 0) == 0 && uri.size() > prefix.size()
        && uri.find('/', prefix.size()) == std::string::npos) {
        const std::string deviceId = uri.substr(prefix.size());
        std::string body;
        if (service.deviceJson(deviceId, body)) {
            sendJson(200, body);
        } else {
            sendJson(404, "{\"error\":\"device_not_found\",\"deviceId\":" + jsonString(deviceId) + "}");
        }
        return;
    }
    sendJson(404, "{\"error\":\"not_found\"}");
}

void ReaderHttp::handleStream() {
    if (!authorized()) return;
    if (clients.size() >= PHONENDO_MAX_SSE_CLIENTS) {
        sendJson(503, "{\"error\":\"too_many_subscribers\"}");
        return;
    }
    SubscriberId id = stream.subscribe();
    if (id == 0) {
        sendJson(503, "{\"error\":\"stream_unavailable\"}");
        return;
    }

    // Respuesta a mano: WebServer no sabe de streaming. Se guarda una copia del
    // WiFiClient (comparte el socket), así que sigue abierto tras el handler.
    WiFiClient client = server.client();
    client.print("HTTP/1.1 200 OK\r\n"
                 "Content-Type: text/event-stream\r\n"
                 "Access-Control-Allow-Origin: *\r\n"
                 "Cache-Control: no-cache\r\n"
                 "X-Accel-Buffering: no\r\n"
                 "Connection: keep-alive\r\n\r\n");
    SseClient sse{client, id, millis()};
    if (!write(sse, sseConnected())) {
        stream.unsubscribe(id);
        return;
    }
    clients.push_back(sse);
    Serial.printf("SSE: suscriptor %u conectado (%u activos)\n",
                  static_cast<unsigned>(id), static_cast<unsigned>(clients.size()));
}

bool ReaderHttp::write(SseClient& sse, const std::string& chunk) {
    if (!sse.client.connected()) return false;
    const size_t written = sse.client.write(reinterpret_cast<const uint8_t*>(chunk.data()), chunk.size());
    sse.lastWrite = millis();
    return written == chunk.size();
}

void ReaderHttp::drainClients() {
    std::string event;
    for (std::size_t i = 0; i < clients.size();) {
        SseClient& sse = clients[i];
        bool keep = sse.client.connected();
        while (keep) {
            const StreamPoll result = stream.poll(sse.id, event);
            if (result == StreamPoll::Event) {
                keep = write(sse, sseObservation(event));
            } else if (result == StreamPoll::Empty) {
                if (millis() - sse.lastWrite >= PHONENDO_SSE_HEARTBEAT_MS) keep = write(sse, sseHeartbeat());
                break;
            } else {
                // Closed: cola desbordada o close(). Unknown: ya no está registrado.
                write(sse, sseStreamClosed());
                keep = false;
            }
        }
        if (keep) {
            i++;
            continue;
        }
        Serial.printf("SSE: suscriptor %u desconectado\n", static_cast<unsigned>(sse.id));
        stream.unsubscribe(sse.id);
        sse.client.stop();
        clients.erase(clients.begin() + i);
    }
}

void ReaderHttp::close() {
    stream.close();
    drainClients();
}
