#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <esp_mac.h>
#include "config.h"
#include "conexion.h"
#include "tipos.h"
#include "pantalla.h"

// ---------- PUERTO ----------
class ISensores {
 public:
  virtual void iniciar() {}
  virtual Lectura leer() = 0;
  virtual ~ISensores() {}
};

// ---------- Calibración ----------
#ifdef SIMULACION
  const int SUELO_AIRE = 4095, SUELO_AGUA = 0;     // el potenciómetro hace de sensor
  const float RL10 = 50.0f;                        // LDR de Wokwi
#else
  const int SUELO_AIRE = 3038, SUELO_AGUA = 1300;  // AIRE medido; AGUA: mídelo en un vaso
  const float RL10 = 15.0f;                        // ajústalo con un luxómetro
#endif
const float GAMMA = 0.7f;
const bool LDR_A_GND = true;  // 3V3 -> 10k -> nodo -> LDR -> GND. Si con más luz bajan los lux: false

int promedio(int pin) {                            // promediar reduce el ruido
  long suma = 0;
  for (int i = 0; i < 32; i++) { suma += analogRead(pin); delay(2); }
  return suma / 32;
}

float luxDesdeLDR(int crudo) {
  crudo = constrain(crudo, 1, 4094);
  float v = crudo * 3.3f / 4095.0f;
  float r = LDR_A_GND ? 10000.0f * v / (3.3f - v)
                      : 10000.0f * (3.3f - v) / v;
  return pow(RL10 * 1000.0f * pow(10.0f, GAMMA) / r, 1.0f / GAMMA);
}

// ---------- ADAPTADOR: sensores (Wokwi y placa real) ----------
class SensoresReales : public ISensores {
  OneWire bus{PIN_TEMP};
  DallasTemperature ds{&bus};
 public:
  void iniciar() override { analogReadResolution(12); ds.begin(); }
  Lectura leer() override {
    float humedad = (SUELO_AIRE - promedio(PIN_SUELO)) * 100.0f / (SUELO_AIRE - SUELO_AGUA);
    humedad = constrain(humedad, 0.0f, 100.0f);
    float luz = luxDesdeLDR(promedio(PIN_LDR));
    ds.requestTemperatures();
    float temp = ds.getTempCByIndex(0);            // -127 = sensor desconectado
    return { humedad, luz, temp };
  }
};

// ---------- ánimo local (respaldo hasta que el backend envíe "mascota") ----------
Animo animoSimulado(const Lectura& l) {
  if (l.humedad < 30) return Animo::SEDIENTA;
  if (l.temperatura > 30) return Animo::ACALORADA;
  if (l.luz < 200) return Animo::DEPRIMIDA;
  return Animo::FELIZ;
}

// ---------- main: "el gerente" decide qué adaptador usar ----------
PantallaOLED pantalla;
SensoresReales sensores;
AlmacenToken almacen;
ConexionWS conexion{almacen};
String mac;

String macComoTexto() {
  uint8_t m[6];
  esp_read_mac(m, ESP_MAC_WIFI_STA);
  char s[18];
  snprintf(s, sizeof(s), "%02X:%02X:%02X:%02X:%02X:%02X", m[0], m[1], m[2], m[3], m[4], m[5]);
  return String(s);
}

String ahoraISO() {                                // el backend exige tomada_en en ISO8601
  time_t t = time(nullptr);
  struct tm tm;
  gmtime_r(&t, &tm);
  char s[26];
  strftime(s, sizeof(s), "%Y-%m-%dT%H:%M:%S+00:00", &tm);
  return String(s);
}

void conectarWifi() {
  pantalla.mostrarMensaje("Conectando", "Wi-Fi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  // Si no conecta en tu SuperMini, prueba: WiFi.setTxPower(WIFI_POWER_8_5dBm);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - t0 > 20000) {
      pantalla.mostrarMensaje("Sin Wi-Fi", "reiniciando...");
      delay(3000);
      ESP.restart();
    }
    delay(300);
  }
}

void sincronizarHora() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  unsigned long t0 = millis();
  while (time(nullptr) < 1700000000 && millis() - t0 < 15000) delay(200);
}

enum class Fase { SERVIDOR, QR, OPERANDO };
Fase faseAnterior = Fase::OPERANDO;
bool dibujada = false;
unsigned long ultimaLectura = 0;

void setup() {
  Serial.begin(115200);
  pantalla.iniciar();
  sensores.iniciar();
  mac = macComoTexto();
  Serial.println("MAC: " + mac);
  conectarWifi();
  sincronizarHora();
  conexion.iniciar(mac);
}

void loop() {
  conexion.ciclo();

  Fase fase = !conexion.conectado ? Fase::SERVIDOR
            : conexion.token.length() == 0 ? Fase::QR
            : conexion.autenticado ? Fase::OPERANDO : Fase::SERVIDOR;
  if (fase != faseAnterior) { faseAnterior = fase; dibujada = false; }

  if (fase == Fase::SERVIDOR && !dibujada) {
    pantalla.mostrarMensaje("Conectando con", "el servidor...");
    dibujada = true;
  } else if (fase == Fase::QR && !dibujada) {
    String url = String(URL_FRONT) + "/?mac=" + mac;
    Serial.printf("QR: %s (largo %d, máximo 53)\n", url.c_str(), url.length());
    pantalla.mostrarQR(url.c_str());
    dibujada = true;
  } else if (fase == Fase::OPERANDO && millis() - ultimaLectura >= INTERVALO_LECTURA_MS) {
    ultimaLectura = millis();
    Lectura l = sensores.leer();
    Serial.printf("H=%.0f L=%.0f T=%.1f\n", l.humedad, l.luz, l.temperatura);
    conexion.enviarLectura(l, ahoraISO());
    pantalla.mostrarMascota(conexion.hayAnimo ? conexion.animo : animoSimulado(l), l);
  }
}