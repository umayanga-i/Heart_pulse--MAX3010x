// ESP32 + MAX30102 raw PPG streamer (research use)
// Library: "SparkFun MAX3010x Pulse and Proximity Sensor Library"
// Wiring: VIN->3V3, GND->GND, SDA->GPIO21, SCL->GPIO22 (INT optional->GPIO19)
#include <Wire.h>
#include "MAX30105.h"

MAX30105 sensor;

const uint16_t SAMPLE_RATE = 200;   // Hz (sensor's own clock times every sample)
uint32_t sampleIndex = 0;

void setup() {
  Serial.begin(921600);
  Wire.begin(21, 22);
  Wire.setClock(400000);

  if (!sensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("ERROR: MAX30102 not found");
    while (true) delay(1000);
  }

  byte ledBrightness = 0x3F;   // tune per subject: raw IR should be ~50k-200k, not saturated (262143)
  byte sampleAverage = 1;      // 1 = no averaging, keep full bandwidth
  byte ledMode       = 2;      // 2 = Red + IR
  int  pulseWidth    = 411;    // 18-bit resolution
  int  adcRange      = 16384;

  sensor.setup(ledBrightness, sampleAverage, ledMode, SAMPLE_RATE, pulseWidth, adcRange);
  sensor.clearFIFO();

  Serial.println("idx,red,ir");
}

void loop() {
  sensor.check();                       // drain FIFO in batches
  while (sensor.available()) {
    Serial.print(sampleIndex++);
    Serial.print(',');
    Serial.print(sensor.getFIFORed());
    Serial.print(',');
    Serial.println(sensor.getFIFOIR());
    sensor.nextSample();
  }
}
