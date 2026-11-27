// Conecta el ESP32 con el backend: recibe y guarda el token,
// autentica el dispositivo y envía las lecturas.
#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "config.h"
#include "tipos.h"

// ---------- ALMACÉN: guarda el token en la memoria no volátil ----------
class AlmacenToken {
  Preferences p;
 public:
  String leer() { p.begin("matera", true); String t = p.getString("token", ""); p.end(); return t; }
  void guardar(const String& t) { p.begin("matera", false); p.putString("token", t); p.end(); }
  void borrar() { p.begin("matera", false); p.remove("token"); p.end(); }
};

// ---------- CONEXIÓN: WebSocket con el backend ----------
class ConexionWS {
  WebSocketsClient ws;
  AlmacenToken& almacen;
  String mac;
  unsigned long reiniciarEn = 0;
  int rechazos = 0;
  // Watchdog de aplicacion: el backend responde cada lectura ("diagnostico" + "mascota", o "error"
  // si la lectura es invalida). Si dejan de llegar respuestas, la conexion esta muerta aunque el
  // socket parezca abierto.
  static const int MAX_LECTURAS_SIN_RESPUESTA = 3;
  int sinRespuesta = 0;

  void enviar(JsonDocument& d) { String s; serializeJson(d, s); ws.sendTXT(s); }

  void alConectar() {
    conectado = true;
    sinRespuesta = 0;
    JsonDocument d;
    d["mac"] = mac;
    if (token.length() > 0) { d["tipo"] = "autenticar"; d["token"] = token; }
    else                    { d["tipo"] = "anuncio"; }
    enviar(d);
  }

  void alMensaje(const char* datos, size_t n) {
    Serial.printf("<- %.*s\n", (int)n, datos);
    JsonDocument d;
    if (deserializeJson(d, datos, n)) return;
    String tipo = d["tipo"] | "";
    // Cualquier mensaje prueba que la conexion vive. No solo "diagnostico"/"mascota": con el
    // DS18B20 desconectado (-127 C) cada lectura recibe "error" y no hay que reconectar en bucle.
    sinRespuesta = 0;

    if (tipo == "token") {
      token = String(d["token"] | "");
      almacen.guardar(token);
      JsonDocument r; r["tipo"] = "token_recibido"; enviar(r);
      reiniciarEn = millis() + 500;
    } else if (tipo == "autenticado") {
      autenticado = true;
      rechazos = 0;
    } else if (tipo == "desvinculado") {
      almacen.borrar();
      token = "";
      reiniciarEn = millis() + 500;            // reinicia, se anuncia y muestra el QR
    } else if (tipo == "error" && !autenticado && token.length() > 0) {
      if (++rechazos >= 3) {                   // el backend ya no reconoce este token
        almacen.borrar();
        token = "";
        reiniciarEn = millis() + 500;
      }
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
  bool conectado = false, autenticado = false, hayAnimo = false;
  String token;
  Animo animo = Animo::FELIZ;

  ConexionWS(AlmacenToken& a) : almacen(a) {}

  void iniciar(const String& miMac) {
    mac = miMac;
    token = almacen.leer();
    ws.onEvent([this](WStype_t t, uint8_t* p, size_t l) {

        if (t == WStype_CONNECTED) {
            Serial.println("[WS] Conexion establecida con el backend");
            alConectar();
        }

        else if (t == WStype_DISCONNECTED) {
            Serial.println("[WS] Conexion perdida o rechazada");
            conectado = false;
            autenticado = false;
        }

        else if (t == WStype_TEXT) {
            Serial.println("[WS] Mensaje recibido");
            alMensaje((const char*)p, l);
        }

        else if (t == WStype_ERROR) {
            Serial.println("[WS] Error en WebSocket");
        }

        else {
            Serial.printf("[WS] Evento: %d\n", (int)t);
        }
    });
#if BACKEND_SSL
    ws.beginSSL(BACKEND_HOST, BACKEND_PORT, BACKEND_WS_PATH);
#else
    ws.begin(BACKEND_HOST, BACKEND_PORT, BACKEND_WS_PATH);
#endif
    ws.setReconnectInterval(5000);
    // Ping cada 15 s; si no llega el pong en 3 s dos veces seguidas, la libreria cierra y reconecta.
    ws.enableHeartbeat(15000, 3000, 2);
  }

  void ciclo() {
    ws.loop();
    if (reiniciarEn && millis() > reiniciarEn) ESP.restart();
  }

  void enviarLectura(const Lectura& l, const String& fecha) {
    JsonDocument d;
    d["tipo"] = "lectura";
    d["humedad"] = l.humedad;
    d["luz"] = l.luz;
    d["temperatura"] = l.temperatura;
    d["tomada_en"] = fecha;
    enviar(d);
    if (++sinRespuesta >= MAX_LECTURAS_SIN_RESPUESTA) {
      Serial.println("[WS] Sin respuesta del backend: reconectando");
      sinRespuesta = 0;
      autenticado = false;                     // la pantalla vuelve a "Conectando con el servidor..."
      ws.disconnect();                         // setReconnectInterval(5000) vuelve a conectar
    }
  }
};