#include <Arduino.h>
#include <ESP8266WiFi.h>

#include <core.h>
#include <device.h>
#include <sensors/temperature_sensor.h>

const char* WIFI_SSID = "DIGIFIBRA-4RE7";
const char* WIFI_PASS = "DtUPRsyPNE";

ReaderConfig config;

ReaderCore reader(
    "reader-esp8266-01",
    "token_manager",
    "http://192.168.1.135:3003",
    config
);

Device device(
    "esp8266-device-01",
    "ESP8266-12F",
    "arduino"
);

TemperatureSensor tempSensor(
    "patient-001",
    5,
    "temperature-sensor-01"
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

    if (!reader.registerDevice(device)) {
        Serial.print("Error registering device: ");
        Serial.println(reader.lastError);
    }
}

void loop() {
    if (tempSensor.shouldPoll()) {
        if (!reader.ingestRawMeasurement(
            device.deviceId,
            tempSensor.sensorId,
            "36.7",
            "2026-05-25T18:30:00Z",
            true
        )) {
            Serial.print("Error ingesting measurement: ");
            Serial.println(reader.lastError);
        }
    }

    delay(1000);
}
