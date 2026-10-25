#include "manager_output.h"

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>

#include "reader_serialization.h"

ManagerOutput::ManagerOutput(const std::string& list, const std::string& token, unsigned long timeoutMs)
    : token(token), timeoutMs(timeoutMs) {
    std::size_t start = 0;
    while (start <= list.size()) {
        std::size_t end = list.find(',', start);
        if (end == std::string::npos) end = list.size();
        std::string url = list.substr(start, end - start);
        while (!url.empty() && (url.back() == ' ' || url.back() == '/')) url.pop_back();
        while (!url.empty() && url.front() == ' ') url.erase(0, 1);
        if (!url.empty()) urls.push_back(url);
        start = end + 1;
    }
}

std::size_t ManagerOutput::managerCount() const {
    return urls.size();
}

bool ManagerOutput::publish(const std::string& readerId, const Observation& observation) {
    if (urls.empty()) return true;
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("Manager: sin WiFi, evento no enviado");
        return false;
    }

    // Sobre del evento más "token", igual que {**body, 'token': ...} en Python.
    std::string body = observationEventToJson(readerId, observation);
    body.pop_back();
    body += ",\"token\":" + jsonString(token) + "}";

    bool success = true;
    for (const auto& base : urls) {
        const std::string url = base + "/newEvent";
        HTTPClient http;
        http.setTimeout(timeoutMs);
        if (!http.begin(url.c_str())) {
            Serial.printf("Manager %s: URL no válida\n", url.c_str());
            success = false;
            continue;
        }
        http.addHeader("Content-Type", "application/json");
        int status = http.POST(reinterpret_cast<uint8_t*>(&body[0]), body.size());
        if (status < 200 || status >= 300) {
            Serial.printf("Manager %s: fallo %d %s\n", url.c_str(), status,
                          status < 0 ? HTTPClient::errorToString(status).c_str() : "");
            success = false;
        }
        http.end();
    }
    return success;
}
