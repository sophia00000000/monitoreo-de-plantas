#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <qrcode.h>
#include "tipos.h"

// ---------- PUERTO: lo que la lógica necesita de una pantalla ----------
class IPantalla {
 public:
  virtual void iniciar() {}
  virtual void mostrarQR(const char* url) = 0;
  virtual void mostrarMascota(Animo animo, const Lectura& l) = 0;
  virtual ~IPantalla() {}
};

// ---------- ADAPTADOR: OLED SSD1306 128x64 ----------
class PantallaOLED : public IPantalla {
  Adafruit_SSD1306 d{128, 64, &Wire, -1};

  void gota(int x, int y) {                           // gota de agua o de sudor
    d.fillTriangle(x, y - 5, x - 3, y, x + 3, y, SSD1306_WHITE);
    d.fillCircle(x, y + 1, 3, SSD1306_WHITE);
  }

  void cara(Animo a) {                                // cara centrada en (32, 32)
    const int cx = 32, cy = 32;
    d.drawCircle(cx, cy, 28, SSD1306_WHITE);
    switch (a) {
      case Animo::FELIZ:
        d.fillCircle(cx - 10, cy - 8, 3, SSD1306_WHITE);
        d.fillCircle(cx + 10, cy - 8, 3, SSD1306_WHITE);
        d.drawCircleHelper(cx, cy + 2, 10, 0x4 | 0x8, SSD1306_WHITE);   // sonrisa
        break;
      case Animo::SEDIENTA:
        d.drawFastHLine(cx - 14, cy - 8, 8, SSD1306_WHITE);             // ojos cansados
        d.drawFastHLine(cx + 6, cy - 8, 8, SSD1306_WHITE);
        d.drawCircle(cx, cy + 10, 4, SSD1306_WHITE);                    // boca abierta
        gota(cx + 20, cy - 14);
        break;
      case Animo::ACALORADA:
        d.drawLine(cx - 14, cy - 12, cx - 8, cy - 8, SSD1306_WHITE);    // ojos > <
        d.drawLine(cx - 14, cy - 4, cx - 8, cy - 8, SSD1306_WHITE);
        d.drawLine(cx + 14, cy - 12, cx + 8, cy - 8, SSD1306_WHITE);
        d.drawLine(cx + 14, cy - 4, cx + 8, cy - 8, SSD1306_WHITE);
        d.drawLine(cx - 8, cy + 10, cx - 3, cy + 7, SSD1306_WHITE);     // boca ondulada
        d.drawLine(cx - 3, cy + 7, cx + 3, cy + 10, SSD1306_WHITE);
        d.drawLine(cx + 3, cy + 10, cx + 8, cy + 7, SSD1306_WHITE);
        gota(cx + 20, cy - 14);
        break;
      case Animo::DEPRIMIDA:
        d.fillCircle(cx - 10, cy - 6, 2, SSD1306_WHITE);
        d.fillCircle(cx + 10, cy - 6, 2, SSD1306_WHITE);
        d.drawLine(cx - 15, cy - 11, cx - 7, cy - 14, SSD1306_WHITE);   // cejas caídas
        d.drawLine(cx + 15, cy - 11, cx + 7, cy - 14, SSD1306_WHITE);
        d.drawCircleHelper(cx, cy + 16, 8, 0x1 | 0x2, SSD1306_WHITE);   // boca triste
        break;
    }
  }

 public:
  void iniciar() override { d.begin(SSD1306_SWITCHCAPVCC, 0x3C); }

  void mostrarQR(const char* url) override {
    QRCode qr;
    uint8_t buf[qrcode_getBufferSize(3)];
    if (qrcode_initText(&qr, buf, 3, ECC_LOW, url) < 0) {
      Serial.println("URL demasiado larga para QR versión 3");
      return;
    }
    d.clearDisplay();
    d.fillRect(0, 0, 128, 64, SSD1306_WHITE);                           // fondo claro
    const int e = 2, x0 = 3, y0 = (64 - qr.size * e) / 2;
    for (uint8_t y = 0; y < qr.size; y++)
      for (uint8_t x = 0; x < qr.size; x++)
        if (qrcode_getModule(&qr, x, y))
          d.fillRect(x0 + x * e, y0 + y * e, e, e, SSD1306_BLACK);
    d.setTextColor(SSD1306_BLACK);
    d.setTextSize(1);
    d.setCursor(68, 14);
    d.print("Escanea\npara\nvincular\ntu matera");
    d.display();
  }

  void mostrarMascota(Animo animo, const Lectura& l) override {
    static const char* nombres[] = {"FELIZ", "SEDIENTA", "ACALORADA", "DEPRIMIDA"};
    d.clearDisplay();
    cara(animo);
    d.setTextColor(SSD1306_WHITE);
    d.setTextSize(1);
    d.setCursor(68, 4);
    d.printf("H:%.0f%%\nL:%.0f lx\nT:%.1fC", l.humedad, l.luz, l.temperatura);
    d.setCursor(68, 50);
    d.print(nombres[(int)animo]);
    d.display();
  }
};