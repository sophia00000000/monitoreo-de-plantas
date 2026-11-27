
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>

// ==========================================
// CONFIGURACION DE PINES - ESP32-C3 SUPERMINI
// ==========================================

#define PIN_OLED_SDA  7
#define PIN_OLED_SCL  6

#define PIN_HUMEDAD   0
#define PIN_LDR       1
#define PIN_TEMP      4

// ==========================================
// CONFIGURACION DE SENSORES
// ==========================================

// Resistencia fija del divisor de voltaje
const float RESISTENCIA_LDR = 10000.0f;

// Valores iniciales para estimar la iluminacion
const float RL10 = 15.0f;
const float GAMMA = 0.7f;

// ==========================================
// OBJETOS
// ==========================================

// Pantalla OLED SH1106 de 128x64
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(
  U8G2_R0,
  U8X8_PIN_NONE
);

// Sensor DS18B20
OneWire bus(PIN_TEMP);
DallasTemperature ds(&bus);

// ==========================================
// FUNCION PARA PROMEDIAR LECTURAS
// ==========================================

int promedio(int pin) {
  long suma = 0;

  for (int i = 0; i < 32; i++) {
    suma += analogRead(pin);
    delay(2);
  }

  return suma / 32;
}

// ==========================================
// CONVERSION DE LDR A LUX
// ==========================================

float calcularLux(int crudo) {

  crudo = constrain(crudo, 1, 4094);

  float voltaje = crudo * 3.3f / 4095.0f;

  // Conexion:
  // 3V3 -> LDR -> NODO -> resistencia 10k -> GND

// LDR del lado de GND: 3V3 -> 10k -> nodo -> LDR -> GND
float resistenciaLDR = RESISTENCIA_LDR * voltaje / (3.3f - voltaje);

  float lux = pow(
    RL10 * 1000.0f * pow(10.0f, GAMMA)
    / resistenciaLDR,
    1.0f / GAMMA
  );

  return lux;
}

// ==========================================
// CONFIGURACION INICIAL
// ==========================================

void setup() {

  Serial.begin(115200);

  // Resolucion ADC de 12 bits
  analogReadResolution(12);

  // Inicializar comunicacion I2C
  Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);

  // Inicializar pantalla OLED
  oled.begin();
  oled.setFont(u8g2_font_6x10_tf);

  // Inicializar sensor de temperatura
  ds.begin();

  Serial.println();
  Serial.println("================================");
  Serial.println("   CALIBRACION DE SENSORES");
  Serial.println("   ESP32-C3 SUPERMINI");
  Serial.println("================================");

  oled.clearBuffer();
  oled.drawStr(0, 20, "Calibracion");
  oled.drawStr(0, 38, "Iniciando sensores...");
  oled.sendBuffer();

  delay(1500);
}

// ==========================================
// BUCLE PRINCIPAL
// ==========================================

void loop() {

  // Leer humedad del suelo y luz
  int suelo = promedio(PIN_HUMEDAD);
  int ldr = promedio(PIN_LDR);

  // Calcular iluminacion
  float iluminacion = calcularLux(ldr);

  // Leer temperatura
  ds.requestTemperatures();
  float temperatura = ds.getTempCByIndex(0);

  // Mostrar resultados en monitor serial
  Serial.printf(
    "SUELO=%d  LDR=%d  LUX=%.1f  TEMP=%.1f\n",
    suelo,
    ldr,
    iluminacion,
    temperatura
  );

  // Mostrar resultados en OLED
  oled.clearBuffer();

  char linea[32];

  snprintf(linea, sizeof(linea), "Suelo: %d", suelo);
  oled.drawStr(0, 12, linea);

  snprintf(linea, sizeof(linea), "LDR: %d", ldr);
  oled.drawStr(0, 25, linea);

  snprintf(linea, sizeof(linea), "Lux: %.1f", iluminacion);
  oled.drawStr(0, 38, linea);

  if (temperatura == DEVICE_DISCONNECTED_C) {
    oled.drawStr(0, 51, "Temp: Error");
  } else {
    snprintf(
      linea,
      sizeof(linea),
      "Temp: %.1f C",
      temperatura
    );
    oled.drawStr(0, 51, linea);
  }

  oled.sendBuffer();

  // Esperar medio segundo
  delay(500);
}
