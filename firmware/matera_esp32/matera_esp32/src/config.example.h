#pragma once

#define URL_FRONT "http://192.168.1.100:5500"

#ifdef SIMULACION
  #define WIFI_SSID "Wokwi-GUEST"
  #define WIFI_PASS ""
#else
  #define WIFI_SSID "NOMBRE_DE_TU_RED"
  #define WIFI_PASS "CONTRASENA_FALSA"
#endif

#define BACKEND_HOST "192.168.1.100"
#define BACKEND_PORT 5000
#define BACKEND_SSL 0
#define BACKEND_WS_PATH "/ws/dispositivos"
#define INTERVALO_LECTURA_MS 5000