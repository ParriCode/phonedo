// Plantilla de credenciales. Cópiala a src/secrets.h (ignorado por git) y rellénala.
#ifndef PHONENDO_SECRETS_H
#define PHONENDO_SECRETS_H

#define WIFI_SSID "mi-red"
#define WIFI_PASSWORD "mi-clave"

#define READER_ID "reader-esp32-01"
// Vacío: el servidor HTTP no pide token. Si no, exige "Authorization: Bearer <token>".
#define READER_TOKEN ""

// URLs de los Managers separadas por comas; vacío = no se envía a ningún Manager.
// Ejemplo: "http://192.168.1.10:3003,http://192.168.1.11:3003"
#define MANAGER_URLS ""
// Va en el campo "token" del cuerpo de /newEvent (API_TOKEN_MANAGER del Manager).
#define MANAGER_TOKEN ""

// GPIO del pulsador (cableado entre el pin y GND). GPIO 0 es el botón BOOT de
// las placas de desarrollo: sirve para probar sin cablear nada.
#define BUTTON_PIN 4

// Pines de los sensores. Sin definir se usan los de cada placa:
// ESP32:    HC-SR04 Trig 26, Echo 27; KY-040 CLK 25, DT 33, SW 32.
// ESP32-S3: HC-SR04 Trig 6,  Echo 7;  KY-040 CLK 15, DT 16, SW 17.
// #define US_TRIG_PIN 26
// #define US_ECHO_PIN 27
// #define US_THRESHOLD_CM 2.0
// #define ENC_CLK_PIN 25
// #define ENC_DT_PIN 33
// #define ENC_SW_PIN 32

#endif
