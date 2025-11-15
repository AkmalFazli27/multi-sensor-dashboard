#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <math.h>  // For NTC calculations

const char* ssid = "Wokwi-GUEST";
const char* password = "";

const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_client_id = "WokwiClient1";

const char* TOPIC_TEMP_AIR = "irrigation/sensor/environment";  
const char* TOPIC_TEMP_SOIL = "irrigation/sensor/soil";  // Publish soil temperature

#define DHTPIN 15
#define DHTTYPE DHT22
#define SOIL_TEMP_PIN 34

#define SERIES_RESISTOR 10000
#define NTC_NOMINAL 10000
#define TEMP_NOMINAL 25
#define B_COEFFICIENT 3950
#define ADC_MAX 4095.0
#define VCC 3.3

WiFiClient espClient;
PubSubClient client(espClient);
DHT dht(DHTPIN, DHTTYPE);

unsigned long lastPublish = 0;
const long publishInterval = 2000;  // 2 seconds

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    
    if (client.connect(mqtt_client_id)) {
      Serial.println("connected");
      Serial.println("Connected to MQTT broker");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5 seconds");
      delay(5000);
    }
  }
}

float readNTCTemperature() {
  int sum = 0;
  for (int i = 0; i < 10; i++) {
    sum += analogRead(SOIL_TEMP_PIN);
    delay(10);
  }
  int rawADC = sum / 10;

  float voltage = (rawADC / ADC_MAX) * VCC;

  float resistance;
  if (voltage > 0.01) {
    resistance = SERIES_RESISTOR * ((VCC / voltage) - 1.0);
  } else {
    resistance = NTC_NOMINAL;
  }

  float steinhart;
  steinhart = resistance / NTC_NOMINAL;
  steinhart = log(steinhart);
  steinhart /= B_COEFFICIENT;
  steinhart += 1.0 / (TEMP_NOMINAL + 273.15);
  steinhart = 1.0 / steinhart;
  steinhart -= 273.15;

  return steinhart;
}

void publishSensorData() {
  float temp_air = dht.readTemperature();
  float humidity = dht.readHumidity();

  float temp_soil = readNTCTemperature();

  int soil_value = analogRead(SOIL_TEMP_PIN);  
  soil_value = map(soil_value, 0, 4095, 1000, 0);  // contoh soil moisture (0–1000)

  // Publish Air Temperature & Humidity
  if (!isnan(temp_air) && !isnan(humidity)) {
    StaticJsonDocument<200> doc;
    doc["soil"] = soil_value;
    doc["temp"] = round(temp_air * 10) / 10.0;
    doc["hum"]  = round(humidity * 10) / 10.0;

    char buffer[200];
    serializeJson(doc, buffer);

    if (client.publish(TOPIC_TEMP_AIR, buffer)) {
      Serial.print("Published Air: ");
      Serial.println(buffer);
    } else {
      Serial.println("Failed to publish environment data");
    }
  } else {
    Serial.println("Failed to read DHT22 sensor");
  }

  // Publish Soil Temperature (NTC)
  if (temp_soil > -10 && temp_soil < 60) {
    StaticJsonDocument<100> docSoil;
    docSoil["temperature"] = round(temp_soil * 10) / 10.0;

    char bufferSoil[100];
    serializeJson(docSoil, bufferSoil);

    if (client.publish(TOPIC_TEMP_SOIL, bufferSoil)) {
      Serial.print("Published Soil: ");
      Serial.println(bufferSoil);
    } else {
      Serial.println("Failed to publish soil temp");
    }
  } else {
    Serial.println("NTC reading out of range");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  dht.begin();
  pinMode(SOIL_TEMP_PIN, INPUT);
  analogReadResolution(12);

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);

  Serial.println("\nSystem ready! Publishing data...\n");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected! Reconnecting...");
    setup_wifi();
  }

  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long currentMillis = millis();
  if (currentMillis - lastPublish >= publishInterval) {
    lastPublish = currentMillis;
    publishSensorData();
  }
}