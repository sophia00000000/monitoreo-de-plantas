#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <esp_mac.h>
#include "tipos.h"
#include "pantalla.h"


class ISensores {
 public:
  virtual void iniciar() {}
  virtual Lectura leer() = 0;
  virtual ~ISensores() {}
};

// ---------- Calibración del sensor de suelo ----------
#ifdef SIMULACION
  const int SUELO_AIRE = 4095, SUELO_AGUA = 0;      // el potenciómetro hace de sensor
#else
  const int SUELO_AIRE = 3000, SUELO_AGUA = 1300;   // CALIBRAR con el sensor real
#endif

// ---------- Utilidades ----------
int promedio(int pin) {                  // promediar reduce el ruido del ADC
  long suma = 0;
  for (int i = 0; i < 16; i++) suma += analogRead(pin);
  return suma / 16;
}

float escalar(int crudo, float desde, float hasta) {
  return desde + (hasta - desde) * (crudo / 4095.0f);
}

// Fórmula de la documentación de Wokwi, adaptada a 3.3 V y 12 bits
float luxDesdeLDR(int crudo) {
  const float GAMMA = 0.7f, RL10 = 50.0f;
  crudo = constrain(crudo, 1, 4094);     // evita dividir entre cero
  float v = crudo / 4095.0f * 3.3f;
  float resistencia = 10000.0f * v / (3.3f - v);
  return pow(RL10 * 1e3f * pow(10, GAMMA) / resistencia, 1 / GAMMA);
}

// ---------- ADAPTADOR A: 3 potenciómetros (respaldo) ----------
class SensoresSimulados : public ISensores {
 public:
  Lectura leer() override {
    return { escalar(promedio(34), 0, 100),
             escalar(promedio(35), 0, 2000),
             escalar(promedio(32), 0, 50) };
  }
};

// ---------- ADAPTADOR B: sensores (corre en Wokwi y en la placa real) ----------
class SensoresReales : public ISensores {
  OneWire bus{4};                        // DS18B20 en GPIO4
  DallasTemperature ds{&bus};
 public:
  void iniciar() override { ds.begin(); }
  Lectura leer() override {
    float humedad = (SUELO_AIRE - promedio(34)) * 100.0f / (SUELO_AIRE - SUELO_AGUA);
    humedad = constrain(humedad, 0.0f, 100.0f);
    float luz = luxDesdeLDR(promedio(35));
    ds.requestTemperatures();
    float temp = ds.getTempCByIndex(0);  // -127 significa sensor desconectado
    return { humedad, luz, temp };
  }
};

// ---------- ánimo simulado (TEMPORAL: doble del backend, se borra en Etapa 3) ----------
Animo animoSimulado(const Lectura& l) {
  if (l.humedad < 30) return Animo::SEDIENTA;
  if (l.temperatura > 30) return Animo::ACALORADA;
  if (l.luz < 200) return Animo::DEPRIMIDA;
  return Animo::FELIZ;
}

// ---------- main: "el gerente" decide qué adaptador usar ----------
const char* URL_FRONT = "http://172.20.10.3:5500";   // IP de tu PC donde sirves el front

PantallaOLED pantalla;
SensoresReales sensores;
bool vinculado = false;          // TEMPORAL: lo cambia el botón; luego vendrá del token guardado
bool pantallaDibujada = false;

String macComoTexto() {
  uint8_t m[6];
  esp_read_mac(m, ESP_MAC_WIFI_STA);
  char s[18];
  snprintf(s, sizeof(s), "%02X:%02X:%02X:%02X:%02X:%02X", m[0], m[1], m[2], m[3], m[4], m[5]);
  return String(s);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  pantalla.iniciar();
  sensores.iniciar();
  pinMode(13, INPUT_PULLUP);
}

void loop() {
  if (digitalRead(13) == LOW) {            // alterna "sin vincular" / "operando"
    vinculado = !vinculado;
    pantallaDibujada = false;
    delay(300);                            // antirrebote simple
  }

  if (!vinculado) {
    if (!pantallaDibujada) {               // el QR se dibuja una sola vez
      String url = String(URL_FRONT) + "/?mac=" + macComoTexto();
      Serial.println(url);
      Serial.printf("Largo del QR: %d (máximo 53)\n", url.length());
      pantalla.mostrarQR(url.c_str());
      pantallaDibujada = true;
    }
  } else {
    Lectura l = sensores.leer();
    pantalla.mostrarMascota(animoSimulado(l), l);
    Serial.printf("H=%.0f L=%.0f T=%.1f\n", l.humedad, l.luz, l.temperatura);
    delay(300);
  }
}