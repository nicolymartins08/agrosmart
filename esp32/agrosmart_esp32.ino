/*
  AgroSmart — exemplo de firmware ESP32
  Bibliotecas: WiFi.h, HTTPClient.h, ArduinoJson (instalar pelo Library Manager).
  IMPORTANTE: ajuste pinos, sensores, token e URL para o hardware real.
  Nunca conecte a bomba diretamente ao GPIO. Use relé/driver e fonte apropriados.
*/
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "NOME_DA_REDE";
const char* WIFI_PASSWORD = "SENHA_DA_REDE";
const char* SERVER_URL = "http://192.168.0.10:5000"; // IP do computador/servidor na rede
const char* DEVICE_ID = "AGRO-001";
const char* DEVICE_TOKEN = "troque-token-esp32-001";

const int RELAY_PIN = 26;            // ajustar conforme circuito
const bool RELAY_ACTIVE_LOW = true;   // muitos módulos de relé são ativos em LOW
const unsigned long MAX_IRRIGATION_MS = 10000UL;
const unsigned long TELEMETRY_INTERVAL_MS = 30000UL;
const unsigned long COMMAND_POLL_INTERVAL_MS = 2000UL;

unsigned long lastTelemetry = 0;
unsigned long lastCommandPoll = 0;
unsigned long irrigationStarted = 0;
bool irrigationOn = false;

// EXEMPLOS: substitua estas funções pelas leituras reais e calibradas dos seus sensores.
float readSoilMoisturePercent() {
  // Exemplo de conversão analógica; calibrar dryRaw/wetRaw com o sensor real.
  const int SENSOR_PIN = 34;
  const int dryRaw = 3200;
  const int wetRaw = 1400;
  int raw = analogRead(SENSOR_PIN);
  float pct = 100.0f * (dryRaw - raw) / (dryRaw - wetRaw);
  return constrain(pct, 0.0f, 100.0f);
}
float readSoilTemperatureC() {
  // TODO: integrar o sensor de temperatura real. Valor sentinela não é uma leitura real.
  return 25.0f;
}
float readSoilPH() {
  // TODO: integrar sensor de pH e calibração com soluções padrão.
  return 6.5f;
}

void setPump(bool enabled) {
  irrigationOn = enabled;
  digitalWrite(RELAY_PIN, (enabled ^ RELAY_ACTIVE_LOW) ? HIGH : LOW);
  if (enabled) irrigationStarted = millis();
}

void sendTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(String(SERVER_URL) + "/api/telemetry");
  http.addHeader("Content-Type", "application/json");
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["device_token"] = DEVICE_TOKEN;
  doc["moisture"] = readSoilMoisturePercent();
  doc["temperature"] = readSoilTemperatureC();
  doc["ph"] = readSoilPH();
  String payload;
  serializeJson(doc, payload);
  int status = http.POST(payload);
  Serial.printf("Telemetria HTTP: %d\n", status);
  http.end();
}

void pollCommand() {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  String url = String(SERVER_URL) + "/api/device/command?device_id=" + DEVICE_ID + "&device_token=" + DEVICE_TOKEN;
  http.begin(url);
  int status = http.GET();
  if (status == HTTP_CODE_OK) {
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, http.getString());
    if (!err) {
      const char* command = doc["command"] | "OFF";
      int seconds = doc["duration_seconds"] | 0;
      if (String(command) == "ON" && !irrigationOn && seconds > 0) {
        setPump(true);
        Serial.printf("Irrigação ligada por até %d segundos\n", min(seconds, 10));
      }
    }
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  setPump(false); // começa sempre desligada
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Conectando ao Wi-Fi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000UL) {
    delay(500); Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("IP do ESP32: "); Serial.println(WiFi.localIP());
  } else {
    Serial.println("Wi-Fi não conectado; reinicie após conferir as credenciais.");
  }
}

void loop() {
  unsigned long now = millis();
  // Corte local de segurança, independente do servidor.
  if (irrigationOn && now - irrigationStarted >= MAX_IRRIGATION_MS) {
    setPump(false);
    Serial.println("Tempo máximo atingido: bomba desligada.");
  }
  if (WiFi.status() == WL_CONNECTED) {
    if (now - lastTelemetry >= TELEMETRY_INTERVAL_MS) {
      lastTelemetry = now; sendTelemetry();
    }
    if (now - lastCommandPoll >= COMMAND_POLL_INTERVAL_MS) {
      lastCommandPoll = now; pollCommand();
    }
  } else {
    setPump(false); // falha de rede: estado seguro desligado
    delay(100);
  }
}
