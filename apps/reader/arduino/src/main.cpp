#include <Arduino.h>
#include <ESP8266WiFi.h>

#include <core.h>
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

bool sendToManager(
    const std::string& ttl,
    const std::string& readerId,
    const std::string& deviceId
) {
    bool ok = manager.sendObservationTTL(
        String(ttl.c_str()),
        String(readerId.c_str()),
        String(deviceId.c_str())
    );

    if (!ok) {
        Serial.print("Error enviando al Manager: ");
        Serial.println(manager.lastError);
    }

    return ok;
}

ReaderCore reader(
    "reader-esp8266-01",
    true,
    true,
    nullptr,
    sendToManager
);

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
bool managerDeviceRegistered = false;

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
        return reader.registerDevice(device);
    }

    return true;
}

bool registerDeviceOnManager() {
    if (managerDeviceRegistered) {
        return true;
    }

    bool ok = manager.registerDevice(
        String(reader.getReaderId().c_str()),
        device
    );

    if (!ok) {
        Serial.print("Error registrando device en Manager: ");
        Serial.println(manager.lastError);
        Serial.print("Respuesta Manager: ");
        Serial.println(manager.lastResponseBody);
        return false;
    }

    managerDeviceRegistered = true;
    Serial.println("Device registrado en Manager.");
    return true;
}

void publishMotion(int motion) {
    Observation observation;

    reader.ingestRawMeasurement(
        device.deviceId,
        pirSensor.sensorId,
        motion == HIGH ? "true" : "false",
        std::to_string(millis()),
        &observation
    );
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

    if (connectWifi()) {
        registerDeviceOnManager();
    }
}

void loop() {
    int motion = digitalRead(PIR_PIN);

    Serial.println(motion == HIGH ? "Movimiento detectado" : "Sin movimiento");

    if (millis() - lastSend >= SEND_INTERVAL) {
        lastSend = millis();

        if (connectWifi() && registerDeviceOnManager()) {
            publishMotion(motion);
        }
    }

    delay(500);
}
