#ifndef PHONENDO_MANAGER_CLIENT_H
#define PHONENDO_MANAGER_CLIENT_H

#include <Arduino.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>


class ManagerClient {
public:
    ManagerClient();

    ManagerClient(
        const String& baseUrl,
        const String& token = "",
        const String& sendObservationPath = "/newEvent",
        unsigned long timeoutMs = 10000
    );

    String baseUrl;
    String token;
    String sendObservationPath;
    unsigned long timeoutMs;

    int lastStatusCode;
    String lastError;
    String lastResponseBody;

    bool sendObservationJSON(
        const String& observation_payload,
        const String& readerId,
        const String& deviceId
    );

private:
    String buildUrl(const String& path) const;

    static void appendJsonString(String& out, const String& value);
    static void appendJsonField(String& out, const char* key, const String& value, bool comma = true);

    bool postJson(const String& url, const String& body);
};

#endif