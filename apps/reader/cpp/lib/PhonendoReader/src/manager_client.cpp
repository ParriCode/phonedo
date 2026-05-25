#include "manager_client.h"

ManagerClient::ManagerClient()
    : baseUrl(""),
      token(""),
      sendObservationPath("/newEvent"),
      timeoutMs(10000),
      lastStatusCode(0),
      lastError(""),
      lastResponseBody("") {
}

ManagerClient::ManagerClient(
    const String& baseUrl,
    const String& token,
    const String& sendObservationPath,
    unsigned long timeoutMs
)
    : baseUrl(baseUrl),
      token(token),
      sendObservationPath(sendObservationPath),
      timeoutMs(timeoutMs),
      lastStatusCode(0),
      lastError(""),
      lastResponseBody("") {

    while (this->baseUrl.endsWith("/")) {
        this->baseUrl.remove(this->baseUrl.length() - 1);
    }
}

String ManagerClient::buildUrl(const String& path) const {
    if (path.startsWith("/")) {
        return baseUrl + path;
    }

    return baseUrl + "/" + path;
}

void ManagerClient::appendJsonString(String& out, const String& value) {
    out += '"';

    for (unsigned int i = 0; i < value.length(); i++) {
        char c = value[i];

        switch (c) {
            case '\\':
                out += F("\\\\");
                break;
            case '"':
                out += F("\\\"");
                break;
            case '\n':
                out += F("\\n");
                break;
            case '\r':
                out += F("\\r");
                break;
            case '\t':
                out += F("\\t");
                break;
            default:
                out += c;
                break;
        }
    }

    out += '"';
}

void ManagerClient::appendJsonField(
    String& out,
    const char* key,
    const String& value,
    bool comma
) {
    out += '"';
    out += key;
    out += F("\":");
    appendJsonString(out, value);

    if (comma) {
        out += ',';
    }
}

void ManagerClient::appendJsonNumberField(
    String& out,
    const char* key,
    unsigned long value,
    bool comma
) {
    out += '"';
    out += key;
    out += F("\":");
    out += String(value);

    if (comma) {
        out += ',';
    }
}

bool ManagerClient::postJson(const String& url, const String& body) {
    lastError = "";
    lastResponseBody = "";
    lastStatusCode = 0;

    if (baseUrl.length() == 0) {
        lastError = "Manager baseUrl is empty";
        return false;
    }

    WiFiClient client;
    HTTPClient http;

    http.setTimeout(timeoutMs);

    if (!http.begin(client, url)) {
        lastError = "HTTP begin failed";
        return false;
    }

    http.addHeader("Accept", "application/json, text/plain");
    http.addHeader("Content-Type", "application/json");

    if (token.length() > 0) {
        http.addHeader("Authorization", "Bearer " + token);
    }

    lastStatusCode = http.POST(body);
    lastResponseBody = http.getString();

    http.end();

    if (lastStatusCode < 200 || lastStatusCode >= 300) {
        lastError = "HTTP error. Status=" + String(lastStatusCode);
        return false;
    }

    return true;
}

bool ManagerClient::sendObservationTTL(
    const String& ttl,
    const String& readerId,
    const String& deviceId
) {
    if (ttl.length() == 0) {
        lastError = "ttl is empty";
        return false;
    }

    if (readerId.length() == 0) {
        lastError = "readerId is empty";
        return false;
    }

    if (deviceId.length() == 0) {
        lastError = "deviceId is empty";
        return false;
    }

    String body;
    body.reserve(ttl.length() + 260);

    body += '{';
    appendJsonField(body, "token", token);
    appendJsonField(body, "eventType", "observation");
    appendJsonField(body, "payloadFormat", "text/turtle");
    appendJsonField(body, "payload", ttl);
    appendJsonField(body, "deviceId", deviceId);
    appendJsonField(body, "readerId", readerId, false);
    body += '}';

    return postJson(buildUrl(sendObservationPath), body);
}

bool ManagerClient::registerDevice(
    const String& readerId,
    const Device& device
) {
    if (readerId.length() == 0) {
        lastError = "readerId is empty";
        return false;
    }

    if (!device.isValid()) {
        lastError = "device is invalid";
        return false;
    }

    String body;
    body.reserve(360);

    body += '{';
    appendJsonField(body, "token", token);
    appendJsonField(body, "schemaVersion", "phonendo.event.v1");
    appendJsonField(body, "readerId", readerId);
    appendJsonField(body, "deviceId", device.deviceId);
    appendJsonField(body, "deviceType", device.deviceType);
    appendJsonField(body, "serialNumber", device.serialNumber);
    appendJsonField(body, "macAddress", device.macAddress);
    appendJsonNumberField(body, "creationDatetime", millis(), false);
    body += '}';

    return postJson(buildUrl("/registerDevice"), body);
}