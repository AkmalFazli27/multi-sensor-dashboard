#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

// WiFi dan MQTT Configuration
const char *ssid = "Wokwi-GUEST";
const char *password = "";
const char *mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char *mqtt_client_id = "ESP32_WaterPumpController";

// MQTT Topics
const char *topic_sensor_data = "irrigation/sensor/water_level";
const char *topic_pump_status = "irrigation/actuator/status";
const char *topic_pump_command = "irrigation/actuator/control";
const char *topic_soil_data = "irrigation/sensor/soil";

// Pin Configuration
#define TRIG_PIN 5
#define ECHO_PIN 18
#define SERVO_PIN 4

// Tank Configuration (dalam cm)
#define TANK_HEIGHT 127    // Tinggi tandon dalam cm (1270mm)
#define MIN_WATER_LEVEL 10 // Minimal level air (cm dari bawah)

// Sensor Thresholds
#define DRY_SOIL_THRESHOLD 400 // Nilai soil moisture untuk tanah kering
#define WET_SOIL_THRESHOLD 600 // Nilai soil moisture untuk tanah lembab

// System Variables
Servo pumpServo;
WiFiClient espClient;
PubSubClient client(espClient);

struct SystemStatus
{
  bool pumpOn = false;
  int servoAngle = 0;
  String mode = "AUTO"; // AUTO atau MANUAL
  float distance = 0;
  int capacityPercent = 0;
  bool systemEnabled = true;
};

SystemStatus systemStatus;

struct SensorData
{
  int soil = 0;
  float temp = 0;
  float hum = 0;
} sensorData;

unsigned long lastSensorRead = 0;
unsigned long lastMQTTPublish = 0;
const unsigned long SENSOR_INTERVAL = 2000; // 2 detik
const unsigned long MQTT_INTERVAL = 5000;   // 5 detik

void setupWiFi()
{
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnectMQTT()
{
  while (!client.connected())
  {
    Serial.print("Attempting MQTT connection...");

    if (client.connect(mqtt_client_id))
    {
      Serial.println("connected");
      // Subscribe to command topics
      client.subscribe(topic_pump_command);
      client.subscribe(topic_soil_data);

      // Add logging for successful subscriptions
      Serial.println("Subscribed to topics:");
      Serial.println("  - " + String(topic_pump_command));
      Serial.println("  - " + String(topic_soil_data));
    }
    else
    {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void controlPump(bool turnOn, int servoAngle)
{
  systemStatus.pumpOn = turnOn;
  systemStatus.servoAngle = servoAngle;

  // Control servo with debugging
  pumpServo.write(servoAngle);
  delay(500); // Give servo time to move
}

void publishPumpStatus()
{
  DynamicJsonDocument doc(1024);
  doc["pump"] = systemStatus.pumpOn ? "ON" : "OFF";
  doc["servo"] = systemStatus.servoAngle;
  doc["mode"] = systemStatus.mode;

  String jsonString;
  serializeJson(doc, jsonString);

  client.publish(topic_pump_status, jsonString.c_str());
  Serial.println("Published pump status: " + jsonString);
}

void handlePumpCommand(String message)
{
  DynamicJsonDocument doc(1024);
  DeserializationError error = deserializeJson(doc, message);

  if (error)
  {
    Serial.println("JSON parsing error for pump command: " + String(error.c_str()));
    return;
  }

  // Manual control override
  systemStatus.mode = "MANUAL";
  Serial.println("Mode changed to MANUAL");

  if (doc.containsKey("pump"))
  {
    String pumpCommand = doc["pump"];
    int servoAngle = doc.containsKey("servo") ? doc["servo"] : (pumpCommand == "ON" ? 90 : 0);

    controlPump(pumpCommand == "ON", servoAngle);
    publishPumpStatus();
  }
}

void handleSoilData(String message)
{
  DynamicJsonDocument doc(1024);
  DeserializationError error = deserializeJson(doc, message);

  if (error)
  {
    Serial.println("JSON parsing error for soil data");
    return;
  }

  // Update sensor data
  if (doc.containsKey("soil"))
    sensorData.soil = doc["soil"];
  if (doc.containsKey("temp"))
    sensorData.temp = doc["temp"];
  if (doc.containsKey("hum"))
    sensorData.hum = doc["hum"];

  Serial.println("Soil data updated: " + String(sensorData.soil) + ", " + String(sensorData.temp) + ", " + String(sensorData.hum));
}

void readDistanceSensor()
{
  // Trigger ultrasonic sensor
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // Read echo with timeout
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout

  if (duration == 0)
  {
    Serial.println("Sensor timeout - using default simulation value");
    // Simulate realistic water tank reading for demo
    systemStatus.distance = 15.0; // Simulate half-full tank
    return;
  }

  float newDistance = duration * 0.034 / 2; // Convert to cm

  // If no object detected (distance too far), simulate realistic tank reading
  if (newDistance > 300)
  {
    Serial.println("No object detected - simulating tank data");
    // Simulate varying water level for demo purposes
    static float simDistance = 10.0;
    static bool increasing = true;

    if (increasing)
    {
      simDistance += 0.5;
      if (simDistance >= 25)
        increasing = false;
    }
    else
    {
      simDistance -= 0.5;
      if (simDistance <= 5)
        increasing = true;
    }

    systemStatus.distance = simDistance;
    Serial.println("Simulated distance: " + String(systemStatus.distance) + "cm");
    return;
  }

  // Use real sensor reading if object detected
  if (newDistance > 0 && newDistance <= TANK_HEIGHT)
  {
    systemStatus.distance = newDistance;
    Serial.println("Real distance: " + String(systemStatus.distance) + "cm");
  }

  // Limit to tank height
  if (systemStatus.distance > TANK_HEIGHT)
  {
    systemStatus.distance = TANK_HEIGHT;
  }
  if (systemStatus.distance < 0)
  {
    systemStatus.distance = 0;
  }
}
void calculateWaterCapacity()
{
  float waterLevel = TANK_HEIGHT - systemStatus.distance;
  if (waterLevel < 0)
    waterLevel = 0;

  systemStatus.capacityPercent = (int)((waterLevel / TANK_HEIGHT) * 100);

  if (systemStatus.capacityPercent > 100)
    systemStatus.capacityPercent = 100;
  if (systemStatus.capacityPercent < 0)
    systemStatus.capacityPercent = 0;
}
void autoControlLogic()
{
  static unsigned long lastAutoCheck = 0;

  // Check every 3 seconds for auto control
  if (millis() - lastAutoCheck < 3000)
    return;
  lastAutoCheck = millis();

  // Safety check: Water tank level
  bool waterSufficient = (TANK_HEIGHT - systemStatus.distance) > MIN_WATER_LEVEL;

  // Determine soil condition
  bool soilDry = sensorData.soil > 0 && sensorData.soil < DRY_SOIL_THRESHOLD;
  bool soilWet = sensorData.soil >= WET_SOIL_THRESHOLD;

  // Control logic
  if (!waterSufficient)
  {
    // Override safety: Air tandon kurang
    if (systemStatus.pumpOn)
    {
      systemStatus.mode = "AUTO";
      controlPump(false, 0);
      publishPumpStatus();
      Serial.println("AUTO: Water tank low - Pump OFF (Safety Override)");
    }
  }
  else if (soilDry && waterSufficient)
  {
    // Tanah kering & air cukup
    if (!systemStatus.pumpOn)
    {
      systemStatus.mode = "AUTO";
      controlPump(true, 90);
      publishPumpStatus();
      Serial.println("AUTO: Soil dry & water sufficient - Pump ON");
    }
  }
  else if (soilWet)
  {
    // Tanah lembab
    if (systemStatus.pumpOn)
    {
      systemStatus.mode = "AUTO";
      controlPump(false, 0);
      publishPumpStatus();
      Serial.println("AUTO: Soil wet - Pump OFF");
    }
  }
}

void publishSensorData()
{
  DynamicJsonDocument doc(1024);
  doc["distance"] = systemStatus.distance;
  doc["capacity_percent"] = systemStatus.capacityPercent;

  String jsonString;
  serializeJson(doc, jsonString);

  bool published = client.publish(topic_sensor_data, jsonString.c_str());

  if (published)
  {
    Serial.println("Published: " + jsonString);
  }
  else
  {
    Serial.println("Publish failed");
  }
}
void mqttCallback(char *topic, byte *payload, unsigned int length)
{
  String message;
  for (int i = 0; i < length; i++)
  {
    message += (char)payload[i];
  }

  Serial.println("Received: " + String(topic) + " = " + message);

  // Handle pump command
  if (String(topic) == topic_pump_command)
  {
    handlePumpCommand(message);
  }

  // Handle soil sensor data
  if (String(topic) == topic_soil_data)
  {
    handleSoilData(message);
  }
}

void setup()
{
  Serial.begin(115200);

  // Initialize pins
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  // Initialize servo with debugging
  Serial.println("Initializing servo on pin " + String(SERVO_PIN));
  pumpServo.attach(SERVO_PIN);
  Serial.println("Servo attached successfully");

  Serial.println("Setting initial servo position to 0 degrees");
  pumpServo.write(0); // Start with servo closed
  delay(1000);        // Give servo time to reach position
  Serial.println("Servo initialized at 0 degrees");

  // Connect to WiFi
  setupWiFi();

  // Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);

  Serial.println("Water Pump Control System Started");

  // Initial sensor reading
  readDistanceSensor();
  calculateWaterCapacity();
  Serial.println("Initial - Distance: " + String(systemStatus.distance) + "cm, Capacity: " + String(systemStatus.capacityPercent) + "%");

  publishPumpStatus();
  publishSensorData();
}

void loop()
{
  // Maintain MQTT connection
  if (!client.connected())
  {
    reconnectMQTT();
  }
  client.loop();

  // Read sensors periodically
  if (millis() - lastSensorRead >= SENSOR_INTERVAL)
  {
    // Store old values for comparison
    float oldDistance = systemStatus.distance;
    int oldCapacity = systemStatus.capacityPercent;

    // Read new sensor data
    readDistanceSensor();
    calculateWaterCapacity();

    // Only show when data changes
    if (oldDistance != systemStatus.distance || oldCapacity != systemStatus.capacityPercent)
    {
      Serial.println("Distance: " + String(systemStatus.distance) + "cm, Capacity: " + String(systemStatus.capacityPercent) + "%");
    }

    lastSensorRead = millis();
  }

  // Publish sensor data periodically
  if (millis() - lastMQTTPublish >= MQTT_INTERVAL)
  {
    publishSensorData();
    lastMQTTPublish = millis();
  }

  // Auto control logic (only if in AUTO mode)
  if (systemStatus.mode == "AUTO")
  {
    autoControlLogic();
  }

  delay(100);
}