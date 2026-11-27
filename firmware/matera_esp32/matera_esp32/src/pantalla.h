#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <qrcode.h>
#include "config.h"
#include "tipos.h"

// ---------- PUERTO: lo que la lógica necesita de una pantalla ----------
class IPantalla {
 public:
  virtual void iniciar() {}
  virtual void mostrarQR(const char* url) = 0;
  virtual void mostrarMascota(Animo animo, const Lectura& l) = 0;
  virtual void mostrarMensaje(const char* l1, const char* l2) = 0;
  virtual ~IPantalla() {}
};

// ---------- ADAPTADOR: OLED 128x64 con U8g2 ----------
class PantallaOLED : public IPantalla {
#ifdef SIMULACION
  U8G2_SSD1306_128X64_NONAME_F_HW_I2C d{U8G2_R0, U8X8_PIN_NONE};
#else
  U8G2_SH1106_128X64_NONAME_F_HW_I2C d{U8G2_R0, U8X8_PIN_NONE};
#endif

  void gota(int x, int y) {
    d.drawTriangle(x, y - 5, x - 3, y, x + 3, y);
    d.drawDisc(x, y + 1, 3);
  }

  void cara(Animo a) {                                   // cara centrada en (32, 32)
    const int cx = 32, cy = 32;
    d.drawCircle(cx, cy, 28);
    switch (a) {
      case Animo::FELIZ:
        d.drawDisc(cx - 10, cy - 8, 3);
        d.drawDisc(cx + 10, cy - 8, 3);
        d.drawCircle(cx, cy + 2, 10, U8G2_DRAW_LOWER_LEFT | U8G2_DRAW_LOWER_RIGHT);   // sonrisa
        break;
      case Animo::SEDIENTA:
        d.drawHLine(cx - 14, cy - 8, 8);
        d.drawHLine(cx + 6, cy - 8, 8);
        d.drawCircle(cx, cy + 10, 4);                                                 // boca abierta
        gota(cx + 20, cy - 14);
        break;
      case Animo::ACALORADA:
        d.drawLine(cx - 14, cy - 12, cx - 8, cy - 8);
        d.drawLine(cx - 14, cy - 4, cx - 8, cy - 8);
        d.drawLine(cx + 14, cy - 12, cx + 8, cy - 8);
        d.drawLine(cx + 14, cy - 4, cx + 8, cy - 8);
        d.drawLine(cx - 8, cy + 10, cx - 3, cy + 7);
        d.drawLine(cx - 3, cy + 7, cx + 3, cy + 10);
        d.drawLine(cx + 3, cy + 10, cx + 8, cy + 7);
        gota(cx + 20, cy - 14);
        break;
      case Animo::DEPRIMIDA:
        d.drawDisc(cx - 10, cy - 6, 2);
        d.drawDisc(cx + 10, cy - 6, 2);
        d.drawLine(cx - 15, cy - 11, cx - 7, cy - 14);
        d.drawLine(cx + 15, cy - 11, cx + 7, cy - 14);
        d.drawCircle(cx, cy + 16, 8, U8G2_DRAW_UPPER_LEFT | U8G2_DRAW_UPPER_RIGHT);   // boca triste
        break;
    }
  }

 public:
  void iniciar() override {
    Wire.begin(PIN_SDA, PIN_SCL);
    d.begin();
    d.setFont(u8g2_font_6x10_tf);
  }

  void mostrarQR(const char* url) override {
    QRCode qr;
    uint8_t buf[qrcode_getBufferSize(3)];
    if (qrcode_initText(&qr, buf, 3, ECC_LOW, url) < 0) {
      Serial.println("URL demasiado larga para QR versión 3");
      return;
    }
    d.clearBuffer();
    d.setDrawColor(1);
    d.drawBox(0, 0, 128, 64);                            // fondo claro
    d.setDrawColor(0);                                   // módulos oscuros
    const int e = 2, x0 = 3, y0 = (64 - qr.size * e) / 2;
    for (uint8_t y = 0; y < qr.size; y++)
      for (uint8_t x = 0; x < qr.size; x++)
        if (qrcode_getModule(&qr, x, y)) d.drawBox(x0 + x * e, y0 + y * e, e, e);
    d.drawStr(68, 16, "Escanea");
    d.drawStr(68, 28, "para");
    d.drawStr(68, 40, "vincular");
    d.drawStr(68, 52, "tu matera");
    d.setDrawColor(1);
    d.sendBuffer();
  }

  void mostrarMascota(Animo animo, const Lectura& l) override {
    static const char* nombres[] = {"FELIZ", "SEDIENTA", "ACALORADA", "DEPRIMIDA"};
    char s[24];
    d.clearBuffer();
    cara(animo);
    snprintf(s, sizeof(s), "H:%.0f%%", l.humedad);        d.drawStr(68, 12, s);
    snprintf(s, sizeof(s), "L:%.0f lx", l.luz);           d.drawStr(68, 24, s);
    snprintf(s, sizeof(s), "T:%.1fC", l.temperatura);     d.drawStr(68, 36, s);
    d.drawStr(68, 60, nombres[(int)animo]);
    d.sendBuffer();
  }

  void mostrarMensaje(const char* l1, const char* l2) override {
    d.clearBuffer();
    d.drawStr(0, 28, l1);
    d.drawStr(0, 42, l2);
    d.sendBuffer();
  }
};