#include <Arduino.h>
#include <ESP8266WiFi.h>

#include <core.h>
#include <device.h>
#include <manager_client.h>
#include <sensor.h>
#include <serializer.h>

const char* WIFI_SSID = "DIGIFIBRA-4RE7";
const char* WIFI_PASS = "DtUPRsyPNE";

ReaderCore reader(
    "reader-esp8266-01"
);

ManagerClient manager(
    "http://192.168.1.135:3003",
    "token_manager"
);

Device device(
    "esp8266-device-01",
    "ESP8266-12F",
    "arduino"
);

Sensor tempSensor(
    "temperatura",
    "temperature-measurement",
    "patient-001",
    "temperature-sensor-01",
    "CELSIUS"
);

void setup() {
    Serial.begin(115200);
    delay(1000);

    WiFi.begin(WIFI_SSID, WIFI_PASS);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.println();
    Serial.println("WiFi connected");

    device.addSensor(tempSensor);

    if (!reader.addDevice(device)) {
        Serial.print("Error adding device: ");
        Serial.println(reader.lastError.c_str());
        return;
    }

    if (!manager.registerDevice(String(reader.readerId.c_str()), device)) {
        Serial.print("Error registering device: ");
        Serial.println(manager.lastError);
    }
}

void loop() {
    Observation observation;
    if (!reader.ingestRawMeasurement(
        device.deviceId,
        tempSensor.sensorId,
        "36.7",
        "2026-05-25T18:30:00Z",
        &observation
    )) {
        Serial.print("Error ingesting measurement: ");
        Serial.println(reader.lastError.c_str());
    } else {
        std::string ttl = serializeSosaTTL(observation);
        if (!manager.sendObservationTTL(
            String(ttl.c_str()),
            String(reader.readerId.c_str()),
            String(observation.deviceId.c_str())
        )) {
            Serial.print("Error sending observation: ");
            Serial.println(manager.lastError);
        }
    }

    delay(1000);
}
