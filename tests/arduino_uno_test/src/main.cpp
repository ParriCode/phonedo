#include <Arduino.h>
#include <SoftwareSerial.h>

#define LED_PIN 2

// RX, TX desde el punto de vista del Arduino
// HC-05 TXD -> D11
// HC-05 RXD <- D10
SoftwareSerial BT(11, 10);

unsigned long lastPing = 0;
bool ledState = false;

void setup() {
    pinMode(LED_PIN, OUTPUT);

    Serial.begin(9600);
    BT.begin(9600);

    delay(1000);

    Serial.println("Arduino listo.");
    Serial.println("Bluetooth listo.");

    BT.println("Hola desde Arduino por Bluetooth");
}

void loop() {
    unsigned long now = millis();

    if (now - lastPing >= 2000) {
        lastPing = now;

        ledState = !ledState;
        digitalWrite(LED_PIN, ledState ? HIGH : LOW);

        Serial.println("[USB] Enviando PING por Bluetooth");
        BT.println("PING desde Arduino");
    }

    // Bluetooth -> USB
    while (BT.available()) {
        char c = BT.read();

        Serial.write(c);

        // Eco hacia Bluetooth para comprobar desde picocom
        BT.write(c);
    }

    // USB -> Bluetooth
    while (Serial.available()) {
        char c = Serial.read();
        BT.write(c);
    }
}