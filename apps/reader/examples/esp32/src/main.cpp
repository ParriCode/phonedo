// Reader Phonendo en ESP32: un dispositivo con cuatro sensores.
//   sensor-1: un entero aleatorio 0–100 cada segundo.
//   sensor-2: una observación por cada pulsación del botón con simple_result 2.
//   sensor-3: distancia en cm de un HC-SR04 (null si no hay eco).
//   sensor-4: encoder rotativo KY-040, {"position","pressed"}.
// Servidor HTTP/SSE con el contrato del Reader Python y envío opcional a uno o
// varios Managers. loop() no usa delay(): el servidor SSE se vacía en cada vuelta.
#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Falta src/secrets.h: copia src/secrets.example.h a src/secrets.h y rellena tus credenciales"
#endif

#include <Arduino.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include <esp_sntp.h>
#include <esp_wifi.h>
#include <cmath>
#include <sys/time.h>
#include <time.h>

#include <core.h>
#include <reader_service.h>
#include <reader_stream.h>

#include "manager_output.h"
#include "reader_http.h"

// Pines por defecto según la placa; CONFIG_IDF_TARGET_* existe tras Arduino.h.
#if CONFIG_IDF_TARGET_ESP32S3
#define US_DEFAULT_TRIG 6
#define US_DEFAULT_ECHO 7
#define ENC_DEFAULT_CLK 15
#define ENC_DEFAULT_DT 16
#define ENC_DEFAULT_SW 17
#else
#define US_DEFAULT_TRIG 26
#define US_DEFAULT_ECHO 27
#define ENC_DEFAULT_CLK 25
#define ENC_DEFAULT_DT 33
#define ENC_DEFAULT_SW 32
#endif

// Botón entre el GPIO y GND (INPUT_PULLUP: pulsado = LOW).
#ifndef BUTTON_PIN
#define BUTTON_PIN 4
#endif
#ifndef US_TRIG_PIN
#define US_TRIG_PIN US_DEFAULT_TRIG
#endif
#ifndef US_ECHO_PIN
#define US_ECHO_PIN US_DEFAULT_ECHO
#endif
// Cambio mínimo (cm) respecto al último valor enviado para volver a enviar.
#ifndef US_THRESHOLD_CM
#define US_THRESHOLD_CM 2.0
#endif
#ifndef ENC_CLK_PIN
#define ENC_CLK_PIN ENC_DEFAULT_CLK
#endif
#ifndef ENC_DT_PIN
#define ENC_DT_PIN ENC_DEFAULT_DT
#endif
#ifndef ENC_SW_PIN
#define ENC_SW_PIN ENC_DEFAULT_SW
#endif

#define DEVICE_ID "esp32-device"
#define MDNS_NAME "phonendo-reader"
#define PERIOD_MS 1000
#define DEBOUNCE_MS 50
#define US_MEASURE_MS 100
#define US_MIN_SEND_MS 200       // como mucho 5 observaciones/s
#define US_ECHO_TIMEOUT_US 25000 // ~4 m ida y vuelta
#define US_MIN_CM 2.0
#define US_MAX_CM 400.0
#define ENC_MIN_SEND_MS 100      // como mucho 10 observaciones/s
#define WIFI_TIMEOUT_MS 20000
#define WIFI_RETRY_MS 10000
#define STREAM_QUEUE_SIZE 16
// Por debajo de esto (año 2023) el reloj aún no se ha sincronizado por NTP.
#define MIN_VALID_EPOCH 1700000000

ObservationStream stream(STREAM_QUEUE_SIZE);
StreamOutput streamOutput(stream);
ManagerOutput managerOutput(MANAGER_URLS, MANAGER_TOKEN);
ReaderCore reader(READER_ID);
ReaderService service(reader, {&streamOutput, &managerOutput});
ReaderHttp http(service, stream, READER_TOKEN);

Device device(DEVICE_ID, "ESP32", "arduino");
// Sensor(observableProperty, procedure, featureOfInterest, sensorId, unit)
Sensor randomSensor("random-value", "random-simulation", DEVICE_ID, "sensor-1");
Sensor buttonSensor("button", "button-press", DEVICE_ID, "sensor-2");
Sensor distanceSensor("distance", "ultrasonic-hcsr04", DEVICE_ID, "sensor-3", "cm");
Sensor encoderSensor("rotary-encoder", "encoder-ky040", DEVICE_ID, "sensor-4");

unsigned long lastPeriodic = 0;
unsigned long lastWifiAttempt = 0;
bool wifiReported = false;

// Antirrebote sin bloquear: el estado cambia solo si la lectura se mantiene DEBOUNCE_MS.
struct Debounced {
    int reading;
    int state;
    unsigned long changedAt;

    // true si el estado estable acaba de cambiar.
    bool update(int pin) {
        const int now = digitalRead(pin);
        if (now != reading) {
            reading = now;
            changedAt = millis();
        }
        if (now != state && millis() - changedAt >= DEBOUNCE_MS) {
            state = now;
            return true;
        }
        return false;
    }
};

Debounced button{HIGH, HIGH, 0};
Debounced encoderSwitch{HIGH, HIGH, 0};

// HC-SR04: NAN significa sin eco o fuera de rango (se publica null).
unsigned long distanceMeasuredAt = 0;
unsigned long distanceSentAt = 0;
bool distanceSent = false;
double distanceSentValue = NAN;

// KY-040: decodificador de cuadratura por tabla de estados en interrupciones.
// Cada muesca (detent) son 4 transiciones válidas de CLK/DT; la ISR las acumula
// y solo cuenta un paso de posición al completar las 4. En reposo el KY-040
// deja CLK y DT en alto, y ahí se resincroniza.
portMUX_TYPE encoderMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint8_t encoderPrevious = 0;
volatile int8_t encoderSteps = 0;
volatile long encoderPosition = 0;
bool encoderSent = false;
long encoderSentPosition = 0;
bool encoderSentPressed = false;
unsigned long encoderSentAt = 0;

// Índice (anterior << 2 | actual) → -1, 0 o +1; 0 también para saltos inválidos.
static const int8_t QUADRATURE[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};

void IRAM_ATTR onEncoderChange() {
    const uint8_t current = (digitalRead(ENC_CLK_PIN) << 1) | digitalRead(ENC_DT_PIN);
    portENTER_CRITICAL_ISR(&encoderMux);
    encoderSteps += QUADRATURE[(encoderPrevious << 2) | current];
    encoderPrevious = current;
    if (encoderSteps >= 4) {
        encoderPosition++;
        encoderSteps = 0;
    } else if (encoderSteps <= -4) {
        encoderPosition--;
        encoderSteps = 0;
    } else if (current == 0b11) {
        // En reposo (CLK y DT altos) se descarta un paso a medias por rebote.
        encoderSteps = 0;
    }
    portEXIT_CRITICAL_ISR(&encoderMux);
}

void onWifiConnected() {
    Serial.print("WiFi conectado. IP=");
    Serial.println(WiFi.localIP());
    // SNTP solo con red: si arranca sin ella, lwIP reencola la misma consulta
    // DNS en ARP hasta desbordar el contador del pbuf y el chip se reinicia.
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    if (MDNS.begin(MDNS_NAME)) {
        MDNS.addService("http", "tcp", 80);
        Serial.println("mDNS: http://" MDNS_NAME ".local/");
    }
}

// Diagnóstico: lista las redes de 2,4 GHz que ve el ESP32. Si WIFI_SSID no
// aparece, el punto de acceso solo emite en 5 GHz o llega demasiado débil.
void scanWifi() {
    const int found = WiFi.scanNetworks();
    Serial.printf("Redes visibles: %d\n", found);
    for (int i = 0; i < found; ++i) {
        Serial.printf("  %-32s canal %2d  %4d dBm%s\n", WiFi.SSID(i).c_str(), WiFi.channel(i),
                      WiFi.RSSI(i), WiFi.SSID(i) == WIFI_SSID ? "  <- configurada" : "");
    }
    WiFi.scanDelete();
}

// Solo en setup(): espera a la primera conexión.
void connectWifi() {
    WiFi.mode(WIFI_STA);
    // España usa los canales 1-13; sin esto el canal 13 puede quedar fuera.
    esp_wifi_set_country_code("ES", true);
    // El motivo de desconexión distingue contraseña mala (15, 202), red no
    // encontrada (201) o rechazo del punto de acceso.
    WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) {
        Serial.printf("WiFi desconectado, motivo %u\n", info.wifi_sta_disconnected.reason);
    }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
    scanWifi();
    Serial.printf("Conectando a WiFi %s", WIFI_SSID);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    lastWifiAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - lastWifiAttempt < WIFI_TIMEOUT_MS) {
        Serial.print(".");
        delay(500);
    }
    Serial.println();
    if (WiFi.status() != WL_CONNECTED) Serial.println("No se pudo conectar a WiFi; se reintenta en segundo plano");
}

// En loop(): reintento sin esperar y aviso de la IP al reconectar.
void watchWifi() {
    const bool connected = WiFi.status() == WL_CONNECTED;
    if (connected && !wifiReported) onWifiConnected();
    if (!connected && wifiReported) {
        Serial.println("WiFi perdido");
        esp_sntp_stop();
    }
    wifiReported = connected;
    if (!connected && millis() - lastWifiAttempt >= WIFI_RETRY_MS) {
        lastWifiAttempt = millis();
        WiFi.reconnect();
    }
}

// Hora actual como ISO UTC. Sin NTP el reloj cuenta desde 1970 al arrancar,
// así que la hora sale en 1970-01-01: se publica igual, pero se avisa.
std::string nowIso(bool& synced) {
    struct timeval now;
    gettimeofday(&now, nullptr);
    synced = now.tv_sec >= MIN_VALID_EPOCH;
    return isoUtcFromEpochMicros(static_cast<std::int64_t>(now.tv_sec) * 1000000 + now.tv_usec);
}

// Crea la observación del sensor con la hora actual; el llamante pone el valor.
bool newObservation(Sensor& sensor, Observation& observation) {
    bool synced = false;
    if (!reader.createObservation(DEVICE_ID, sensor.sensorId, "", nowIso(synced), &observation)) {
        Serial.printf("Observación: %s\n", reader.getLastError().c_str());
        return false;
    }
    if (!synced) Serial.println("Aviso: NTP sin sincronizar, phenomenon_time en 1970");
    return true;
}

void send(const Observation& observation) {
    if (!service.ingest(observation)) {
        Serial.printf("Ingest: %s\n", reader.getLastError().empty()
                                          ? "algún Manager no recibió el evento"
                                          : reader.getLastError().c_str());
    }
}

void publishInteger(Sensor& sensor, long long value) {
    Observation observation;
    if (!newObservation(sensor, observation)) return;
    observation.setInteger(value);
    send(observation);
}

void watchButton() {
    // Un evento por pulsación, en el flanco de bajada; mantenerlo no repite.
    if (button.update(BUTTON_PIN) && button.state == LOW) {
        Serial.println("Botón pulsado");
        publishInteger(buttonSensor, 2);
    }
}

// Distancia en cm con un decimal, o NAN si no hay eco o está fuera de rango.
// pulseIn bloquea como mucho US_ECHO_TIMEOUT_US (25 ms).
double measureDistance() {
    digitalWrite(US_TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(US_TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(US_TRIG_PIN, LOW);
    const unsigned long echo = pulseIn(US_ECHO_PIN, HIGH, US_ECHO_TIMEOUT_US);
    if (echo == 0) return NAN;
    // Sonido a 343 m/s: 0,0343 cm/µs, ida y vuelta.
    const double cm = echo * 0.0343 / 2.0;
    if (cm < US_MIN_CM || cm > US_MAX_CM) return NAN;
    return std::round(cm * 10.0) / 10.0;
}

void watchDistance() {
    if (millis() - distanceMeasuredAt < US_MEASURE_MS) return;
    distanceMeasuredAt = millis();
    const double cm = measureDistance();

    if (distanceSent) {
        if (millis() - distanceSentAt < US_MIN_SEND_MS) return;
        const bool wasNull = std::isnan(distanceSentValue);
        const bool isNull = std::isnan(cm);
        const bool changed = wasNull != isNull
            || (!isNull && std::fabs(cm - distanceSentValue) >= US_THRESHOLD_CM);
        if (!changed) return;
    }

    Observation observation;
    if (!newObservation(distanceSensor, observation)) return;
    if (std::isnan(cm)) {
        observation.setNull();
    } else {
        observation.setNumber(cm);
    }
    distanceSent = true;
    distanceSentValue = cm;
    distanceSentAt = millis();
    send(observation);
}

void watchEncoder() {
    encoderSwitch.update(ENC_SW_PIN);
    if (encoderSent && millis() - encoderSentAt < ENC_MIN_SEND_MS) return;

    portENTER_CRITICAL(&encoderMux);
    const long position = encoderPosition;
    portEXIT_CRITICAL(&encoderMux);
    const bool pressed = encoderSwitch.state == LOW;
    if (encoderSent && position == encoderSentPosition && pressed == encoderSentPressed) return;

    // Tras una ráfaga se envía solo la última posición.
    Observation observation;
    if (!newObservation(encoderSensor, observation)) return;
    observation.setRawJson("{\"position\":" + std::to_string(position)
                           + ",\"pressed\":" + (pressed ? "true" : "false") + "}");
    encoderSent = true;
    encoderSentPosition = position;
    encoderSentPressed = pressed;
    encoderSentAt = millis();
    send(observation);
}

void setupPins() {
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(US_TRIG_PIN, OUTPUT);
    digitalWrite(US_TRIG_PIN, LOW);
    pinMode(US_ECHO_PIN, INPUT);
    // El KY-040 ya trae pull-ups a "+"; los internos no estorban.
    pinMode(ENC_CLK_PIN, INPUT_PULLUP);
    pinMode(ENC_DT_PIN, INPUT_PULLUP);
    pinMode(ENC_SW_PIN, INPUT_PULLUP);
    encoderPrevious = (digitalRead(ENC_CLK_PIN) << 1) | digitalRead(ENC_DT_PIN);
    attachInterrupt(digitalPinToInterrupt(ENC_CLK_PIN), onEncoderChange, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENC_DT_PIN), onEncoderChange, CHANGE);
    randomSeed(esp_random());

    Serial.printf("Botón: GPIO %d\n", BUTTON_PIN);
    Serial.printf("HC-SR04: Trig GPIO %d, Echo GPIO %d\n", US_TRIG_PIN, US_ECHO_PIN);
    Serial.printf("KY-040: CLK GPIO %d, DT GPIO %d, SW GPIO %d\n", ENC_CLK_PIN, ENC_DT_PIN, ENC_SW_PIN);
}

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.printf("Reader %s\n", READER_ID);
    setupPins();

    if (!service.isAttached()) Serial.println(service.getLastError().c_str());
    device.addSensor(randomSensor);
    device.addSensor(buttonSensor);
    device.addSensor(distanceSensor);
    device.addSensor(encoderSensor);
    if (!reader.addDevice(device)) Serial.println(reader.getLastError().c_str());
    Serial.printf("Managers configurados: %u\n", static_cast<unsigned>(managerOutput.managerCount()));

    connectWifi();
    http.begin();
    Serial.println("Servidor HTTP en el puerto 80: /health /metadata /devices /stream");
}

void loop() {
    watchWifi();
    http.poll();
    watchButton();
    watchEncoder();
    watchDistance();
    if (millis() - lastPeriodic >= PERIOD_MS) {
        lastPeriodic = millis();
        publishInteger(randomSensor, random(0, 101));
    }
}
