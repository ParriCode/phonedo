#include <Arduino.h>
#include <ESP8266WiFi.h>

#include <core.h>
#include <device.h>
#include <manager_client.h>
#include <sensor.h>
#include <serializer.h>


#define PHONENDO_WIFI_SSID "CEATIC"
#define PHONENDO_WIFI_PASS "Pd@CEATIC2k16"

#define PHONENDO_MANAGER_URL "http://192.168.83.148:3003"

#define PHONENDO_MANAGER_TOKEN "token_manager"

#define PIR_PIN D1

const unsigned long WIFI_CONNECT_TIMEOUT_MS = 20000;
const unsigned long INTERVAL = 1000;

ReaderCore reader("reader-esp8266-01");

ManagerClient manager(
    PHONENDO_MANAGER_URL,
    PHONENDO_MANAGER_TOKEN
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

bool deviceRegistered = false;
unsigned long last_send = 0;


//Conectar por wify
bool connectWifi() {
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }

    Serial.print("Conectando a WiFi");
    WiFi.mode(WIFI_STA);
    WiFi.begin(PHONENDO_WIFI_SSID, PHONENDO_WIFI_PASS);

    Serial.println();

    Serial.print("WiFi conectado. IP=");
    Serial.println(WiFi.localIP());
    return true;
}

bool publishMotion(int motion) {
   
    Observation observation;
    const std::string rawValue = motion == HIGH ? "true" : "false";
    const String millisText = String(millis());
    const std::string phenomenonTime(millisText.c_str());

    reader.ingestRawMeasurement(
        device.deviceId,
        pirSensor.sensorId,
        rawValue,
        phenomenonTime,
        &observation
    );

    const std::string ttl = serializeSosaTTL(observation);
    if (!manager.sendObservationTTL(
        String(ttl.c_str()),
        String(reader.readerId.c_str()),
        String(observation.deviceId.c_str())
    )) {
        Serial.print("Error enviando observacion al Manager: INICIANDO NUEVO REGISTRO ");
        
        if (reader.registerDevice(device)  && device.addSensor(pirSensor)) {

            connectWifi();
        } else {
            Serial.println("Error registrando device o sensor en ReaderCore.");
        }
        Serial.println(manager.lastError);
        return false;
    }

    Serial.println("Observacion enviada al Manager.");
    return true;
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    pinMode(PIR_PIN, INPUT);

    Serial.println("Iniciando sensor PIR...");
    Serial.println("Espera 30-60 segundos a que se estabilice.");
    //Registrar dispositivo y sensores en el Reader

    if (reader.registerDevice(device)  && device.addSensor(pirSensor)) {
        connectWifi();
    } else {
        Serial.println("Error registrando device o sensor en ReaderCore.");
    }
}

void loop() {
    const int motion = digitalRead(PIR_PIN);

    if (motion == HIGH) {
        Serial.println("Movimiento detectado");
    } else {
        Serial.println("Sin movimiento");
    }

    const unsigned long now = millis();
    if (now - last_send >= INTERVAL) {
        last_send = now;
        publishMotion(motion);
    }

    delay(500);
}
