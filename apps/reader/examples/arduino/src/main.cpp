#include <Arduino.h>
#include <ESP8266WiFi.h>

#include <reader_service.h>
#include "manager_output.h"
#include <device.h>
#include <manager_client.h>
#include <sensor.h>

#define WIFI_SSID "CEATIC"
#define WIFI_PASS "Pd@CEATIC2k16"
#define MANAGER_URL "http://192.168.83.148:3003"
#define MANAGER_TOKEN "token_manager"

#define PIR_PIN D1
#define SEND_INTERVAL 1000
#define WIFI_TIMEOUT 20000

ManagerClient manager(MANAGER_URL, MANAGER_TOKEN);

ManagerOutput managerOutput(manager);
ReaderCore reader("reader-esp8266-01");
ReaderService service(reader, {&managerOutput});

Device device(
    "esp8266-device-01",
    "ESP8266",
    "arduino"
);

Sensor pirSensor(
    "motion",
    "pir-motion-detection",
    "esp8266-device-01",
    "pir-motion-sensor-01"
);

unsigned long lastSend = 0;

bool connectWifi() {
    if (WiFi.status() == WL_CONNECTED) return true;

    Serial.print("Conectando a WiFi");
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    unsigned long start = millis();

    while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT) {
        Serial.print(".");
        delay(500);
    }

    Serial.println();

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("No se pudo conectar a WiFi");
        return false;
    }

    Serial.print("WiFi conectado. IP=");
    Serial.println(WiFi.localIP());

    return true;
}

bool setupReader() {
    if (!device.hasSensor(pirSensor.sensorId)) {
        device.addSensor(pirSensor);
    }

    if (!reader.hasDevice(device.deviceId)) {
        return reader.addDevice(device);
    }

    return true;
}

void publishMotion(int motion) {
    Observation observation;

    if (reader.createObservation(
        device.deviceId,
        pirSensor.sensorId,
        motion == HIGH ? "true" : "false",
        std::to_string(millis()),
        &observation
    )) {
        if (!service.ingest(observation)) {
            Serial.println(reader.getLastError().c_str());
            Serial.println(manager.lastError);
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    pinMode(PIR_PIN, INPUT);

    Serial.println("Iniciando sensor PIR...");
    Serial.println("Espera 30-60 segundos a que se estabilice.");

    if (!setupReader()) {
        Serial.println(reader.getLastError().c_str());
    }

    connectWifi();
}

void loop() {
    int motion = digitalRead(PIR_PIN);

    Serial.println(motion == HIGH ? "Movimiento detectado" : "Sin movimiento");

    if (millis() - lastSend >= SEND_INTERVAL) {
        lastSend = millis();

        if (connectWifi()) {
            publishMotion(motion);
        }
    }

    delay(500);
}
