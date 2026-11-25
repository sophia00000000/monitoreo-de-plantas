#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <esp_mac.h>
#include "tipos.h"
#include "pantalla.h"
#include "config.h"
#include "conexion.h"


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


// Ánimo local: respaldo mientras el backend no envíe el estado de la mascota
Animo animoSimulado(const Lectura& l) {
  if (l.humedad < 30) return Animo::SEDIENTA;
  if (l.temperatura > 30) return Animo::ACALORADA;
  if (l.luz < 200) return Animo::DEPRIMIDA;
  return Animo::FELIZ;
}

// Objetos principales
PantallaOLED pantalla;
SensoresReales sensores;  // Si aún no tienes sensores, usa SensoresSimulados
AlmacenToken almacen;
ConexionWS conexion{almacen};

String mac;

String macComoTexto() {
  uint8_t m[6];
  esp_read_mac(m, ESP_MAC_WIFI_STA);

  char s[18];
  snprintf(s, sizeof(s),
    "%02X:%02X:%02X:%02X:%02X:%02X",
    m[0], m[1], m[2], m[3], m[4], m[5]);

  return String(s);
}

// Fecha y hora en formato ISO 8601
String ahoraISO() {
  time_t t = time(nullptr);
  struct tm tm;
  gmtime_r(&t, &tm);

  char s[26];
  strftime(s, sizeof(s), "%Y-%m-%dT%H:%M:%S+00:00", &tm);

  return String(s);
}

// Conexión Wi-Fi
void conectarWifi() {
  pantalla.mostrarMensaje("Conectando", "Wi-Fi...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  unsigned long t0 = millis();

  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - t0 > 20000) {
      pantalla.mostrarMensaje("Sin Wi-Fi", "reiniciando...");
      delay(3000);
      ESP.restart();
    }

    delay(300);
  }

  Serial.println("Wi-Fi conectado");
  Serial.println(WiFi.localIP());
}

// Sincronización de hora mediante NTP
void sincronizarHora() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  unsigned long t0 = millis();

  while (time(nullptr) < 1700000000 &&
         millis() - t0 < 15000) {
    delay(200);
  }
}

// Estados de funcionamiento
enum class Fase {
  SERVIDOR,
  QR,
  OPERANDO
};

Fase faseAnterior = Fase::OPERANDO;
bool dibujada = false;
unsigned long ultimaLectura = 0;

void setup() {
  Serial.begin(115200);

  Wire.begin(21, 22);

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

  Fase fase = !conexion.conectado
    ? Fase::SERVIDOR
    : conexion.token.length() == 0
      ? Fase::QR
      : conexion.autenticado
        ? Fase::OPERANDO
        : Fase::SERVIDOR;

  if (fase != faseAnterior) {
    faseAnterior = fase;
    dibujada = false;
  }

  if (fase == Fase::SERVIDOR && !dibujada) {
    pantalla.mostrarMensaje("Conectando con", "el servidor...");
    dibujada = true;

  } else if (fase == Fase::QR && !dibujada) {
    String url = String(URL_FRONT) + "/?mac=" + mac;

    Serial.printf("QR: %s (largo %d, máximo 53)\n",
      url.c_str(), url.length());

    pantalla.mostrarQR(url.c_str());
    dibujada = true;

  } else if (fase == Fase::OPERANDO &&
             millis() - ultimaLectura >= INTERVALO_LECTURA_MS) {

    ultimaLectura = millis();

    Lectura l = sensores.leer();

    conexion.enviarLectura(l, ahoraISO());

    pantalla.mostrarMascota(
      conexion.hayAnimo ? conexion.animo : animoSimulado(l),
      l
    );
  }
}
