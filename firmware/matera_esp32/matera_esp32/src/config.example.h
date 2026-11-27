// Plantilla de configuracion del firmware. Copiela como config.h (ignorado por git) y edite los valores.
#pragma once

// ---------- Red ----------
#ifdef SIMULACION
  #define WIFI_SSID "Wokwi-GUEST"
  #define WIFI_PASS ""
#else
  #define WIFI_SSID "NOMBRE_DE_TU_RED"           // red de 2.4 GHz: el ESP32 no ve redes de 5 GHz
  #define WIFI_PASS "CONTRASENA_DE_TU_RED"
#endif

// ---------- Backend y front ----------
// IP del PC donde corre `python Main.py` (ipconfig -> Direccion IPv4). En Wokwi: "host.wokwi.internal".
#define BACKEND_HOST "192.168.1.100"
#define BACKEND_PORT 5000
#define BACKEND_SSL 0                            // 1 si el backend usa MATERA_SSL_CERT (WSS)
#define BACKEND_WS_PATH "/ws/dispositivos"
// Direccion con la que se abre el front, sin barra final. El QR de la pantalla apunta aqui.
#define URL_FRONT "http://192.168.1.100:5500"

#define INTERVALO_LECTURA_MS 5000

// ---------- Pines ----------
#ifdef SIMULACION                                // diagram.json (ESP32 DevKit C en Wokwi)
  #define PIN_SUELO 34                           // potenciometro = sensor de humedad
  #define PIN_LDR   35
  #define PIN_TEMP  4                            // DS18B20
  #define PIN_SDA   21                           // OLED SSD1306
  #define PIN_SCL   22
#else                                            // ESP32-C3 SuperMini (mismos pines que calibracion.cpp)
  #define PIN_SUELO 0
  #define PIN_LDR   1
  #define PIN_TEMP  4
  #define PIN_SDA   7                            // OLED SH1106
  #define PIN_SCL   6
#endif
