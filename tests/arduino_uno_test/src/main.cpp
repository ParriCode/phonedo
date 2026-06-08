#include <Arduino.h>
#include <SoftwareSerial.h>
#include <DHT.h>

#define LED_PIN 2
#define DHT_PIN 3
#define DHT_TYPE DHT11
#define LIGHT_PIN A0
#define JOY_BUTTON_PIN 4
#define JOY_Y_PIN A1
#define JOY_X_PIN A2
#define BT_BAUD 9600
#define DHT_STARTUP_DELAY_MS 2000

#define PIN_TRIG = 12
#define PIN_ECHO = 13

#define DEVICE_ID "prueba2"

SoftwareSerial BT(11, 10); // RX, TX
DHT dht(DHT_PIN, DHT_TYPE);

bool ledState = false;

float interval_time = 1000; // Tiempo de lectura de sensores en ms
unsigned long lastSensorSendTime = 0;

// Estados anteriores del joystick
int joyButtonState = -1;
int joyXState = -1;
int joyYState = -1;

// Margen para evitar ruido en el joystick analógico
const int JOY_EVENT_DELTA = 20;


const float SOUND_SPEED = 343.0; // Velocidad del sonido en m/s

float distance;

void sendObservation(
    Print &out,
    const char *sensorId,
    const char *observableProperty,
    const char *procedure,
    const char *unit,
    float value
) {
    out.print(F("{\"device_id\":\""));
    out.print(DEVICE_ID);
    out.print(F("\",\"sensor_id\":\""));
    out.print(sensorId);
    out.print(F("\",\"observable_property\":\""));
    out.print(observableProperty);
    out.print(F("\",\"procedure\":\""));
    out.print(procedure);
    out.print(F("\",\"feature_of_interest\":\"patient-001\""));

    if (unit != nullptr && unit[0] != '\0') {
        out.print(F(",\"unit\":\""));
        out.print(unit);
        out.print(F("\""));
    }

    out.print(F(",\"value\":"));
    out.print(value);
    out.println(F("}"));
}

void logReading(float temperature, float humidity, int lightValue, int joyX, int joyY, int joyButton) {
    Serial.println(F("---- Arduino sensor test ----"));

    Serial.print(F("DHT pin: "));
    Serial.println(DHT_PIN);

    Serial.print(F("temperature raw: "));
    Serial.println(temperature);

    Serial.print(F("humidity raw: "));
    Serial.println(humidity);

    Serial.print(F("light raw: "));
    Serial.println(lightValue);

    Serial.print(F("joystick x raw: "));
    Serial.println(joyX);

    Serial.print(F("joystick y raw: "));
    Serial.println(joyY);

    Serial.print(F("joystick button pressed: "));
    Serial.println(joyButton);

    if (isnan(temperature)) {
        Serial.println(F("ERROR: DHT temperature is NaN. Check wiring, pin, power, sensor type."));
    }

    if (isnan(humidity)) {
        Serial.println(F("ERROR: DHT humidity is NaN. Check wiring, pin, power, sensor type."));
    }
}

void logSent(const char *sensorId) {
    Serial.print(F("BT sent: "));
    Serial.println(sensorId);
}

void sendJoystickEvents(int joyX, int joyY, int joyButton) {
    if (joyButtonState != joyButton) {
        joyButtonState = joyButton;

        sendObservation(
            BT,
            "joy_button",
            "joystick_button",
            "joystick_digital",
            "",
            joyButton
        );

        logSent("joy_button");
    }

    if ( abs(joyX - joyXState) >= JOY_EVENT_DELTA) {
        joyXState = joyX;

        sendObservation(
            BT,
            "joy_x",
            "joystick_x",
            "joystick_analog",
            "",
            joyX
        );

        logSent("joy_x");
    }

    if ( abs(joyY - joyYState) >= JOY_EVENT_DELTA) {
        joyYState = joyY;

        sendObservation(
            BT,
            "joy_y",
            "joystick_y",
            "joystick_analog",
            "",
            joyY
        );

        logSent("joy_y");
    }
}

void sendTimedSensorReadings(int joyX, int joyY, int joyButton) {
    int lightValue = analogRead(LIGHT_PIN);

    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();

    bool hasTemperature = !isnan(temperature);
    bool hasHumidity = !isnan(humidity);

    logReading(temperature, humidity, lightValue, joyX, joyY, joyButton);

    if (hasTemperature) {
        sendObservation(
            BT,
            "temp1",
            "temperatura",
            "dht11",
            "CELSIUS",
            temperature
        );

        logSent("temp1");
    }

    if (hasHumidity) {
        sendObservation(
            BT,
            "hum1",
            "humedad",
            "dht11",
            "PERCENT",
            humidity
        );

        logSent("hum1");
    }

    sendObservation(
        BT,
        "light1",
        "luz",
        "ldr",
        "",
        lightValue
    );

    logSent("light1");

    ledState = !ledState;
    digitalWrite(LED_PIN, ledState ? HIGH : LOW);
}

void setup() {
    pinMode(LED_PIN, OUTPUT);
    pinMode(LIGHT_PIN, INPUT);
    pinMode(JOY_X_PIN, INPUT);
    pinMode(JOY_Y_PIN, INPUT);
    pinMode(JOY_BUTTON_PIN, INPUT_PULLUP);
    PinMode(PIN_TRIG, OUTPUT);
    PinMode(PIN_ECHO, INPUT);

    Serial.begin(9600);
    BT.begin(BT_BAUD);

    dht.begin();
    delay(DHT_STARTUP_DELAY_MS);

    Serial.println(F("Arduino test ready"));

    Serial.print(F("Device: "));
    Serial.println(DEVICE_ID);

    Serial.print(F("Bluetooth baud: "));
    Serial.println(BT_BAUD);
}

void loop() {
    unsigned long now = millis();

    int joyX = analogRead(JOY_X_PIN);
    int joyY = analogRead(JOY_Y_PIN);
    int joyButton = digitalRead(JOY_BUTTON_PIN) == LOW ? 1 : 0;

    // Joystick por eventos
    sendJoystickEvents(joyX, joyY, joyButton);

    // Sensores por tiempo
    if (now - lastSensorSendTime >= (unsigned long)interval_time) {
        lastSensorSendTime = now;
        sendTimedSensorReadings(joyX, joyY, joyButton);
    }
}