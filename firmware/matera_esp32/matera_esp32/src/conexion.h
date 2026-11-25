// conecta el ESP32 con el backend, recibir y guardar el token, 
// autenticar el dispositivo y enviar las lecturas.
#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "config.h"
#include "tipos.h"

// Guarda el token en la memoria del ESP32
class AlmacenToken {
  Preferences p;

 public:
  String leer() {
    p.begin("matera", true);
    String t = p.getString("token", "");
    p.end();
    return t;
  }

  void guardar(const String& t) {
    p.begin("matera", false);
    p.putString("token", t);
    p.end();
  }

  void borrar() {
    p.begin("matera", false);
    p.remove("token");
    p.end();
  }
};

// Gestiona la conexión WebSocket con el backend
class ConexionWS {
  WebSocketsClient ws;
  AlmacenToken& almacen;
  String mac;
  unsigned long reiniciarEn = 0;

  void enviar(JsonDocument& d) {
    String s;
    serializeJson(d, s);
    ws.sendTXT(s);
  }

  void alConectar() {
    conectado = true;

    JsonDocument d;
    d["mac"] = mac;

    if (token.length() > 0) {
      d["tipo"] = "autenticar";
      d["token"] = token;
    } else {
      d["tipo"] = "anuncio";
    }

    enviar(d);
  }

  void alMensaje(const char* datos, size_t n) {
    Serial.printf("<- %.*s\n", (int)n, datos);

    JsonDocument d;
    if (deserializeJson(d, datos, n)) return;

    String tipo = d["tipo"] | "";

    if (tipo == "token") {
      token = String(d["token"] | "");
      almacen.guardar(token);

      JsonDocument r;
      r["tipo"] = "token_recibido";
      enviar(r);

      reiniciarEn = millis() + 500;

    } else if (tipo == "autenticado") {
      autenticado = true;

    } else if (tipo == "mascota") {
      String a = d["animo"] | "";

      if (a == "FELIZ") animo = Animo::FELIZ;
      else if (a == "SEDIENTA") animo = Animo::SEDIENTA;
      else if (a == "ACALORADA") animo = Animo::ACALORADA;
      else if (a == "DEPRIMIDA") animo = Animo::DEPRIMIDA;
      else return;

      hayAnimo = true;
    }
  }

 public:
  bool conectado = false;
  bool autenticado = false;
  bool hayAnimo = false;

  String token;
  Animo animo = Animo::FELIZ;

  ConexionWS(AlmacenToken& a) : almacen(a) {}

  void iniciar(const String& miMac) {
    mac = miMac;
    token = almacen.leer();

    ws.onEvent([this](WStype_t t, uint8_t* p, size_t l) {
      if (t == WStype_CONNECTED) {
        alConectar();
      } else if (t == WStype_DISCONNECTED) {
        conectado = false;
        autenticado = false;
      } else if (t == WStype_TEXT) {
        alMensaje((const char*)p, l);
      }
    });

#if BACKEND_SSL
    ws.beginSSL(BACKEND_HOST, BACKEND_PORT, BACKEND_WS_PATH);
#else
    ws.begin(BACKEND_HOST, BACKEND_PORT, BACKEND_WS_PATH);
#endif

    ws.setReconnectInterval(5000);
  }

  void ciclo() {
    ws.loop();

    if (reiniciarEn && millis() > reiniciarEn) {
      ESP.restart();
    }
  }

  void enviarLectura(const Lectura& l, const String& fecha) {
    JsonDocument d;

    d["tipo"] = "lectura";
    d["humedad"] = l.humedad;
    d["luz"] = l.luz;
    d["temperatura"] = l.temperatura;
    d["tomada_en"] = fecha;

    enviar(d);
  }
};
