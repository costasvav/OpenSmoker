// ********************************************************************************************************************
// OpenSmoker
// ********************************************************************************************************************
//
// Author: Constantine Vavourakis
// Date: 2025-03-14
//
// Copyright (C) 2025 
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.
//
// ********************************************************************************************************************
// Imports
// ********************************************************************************************************************

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_MAX31865.h>
#include <Adafruit_MCP9600.h>
#include <hardware/watchdog.h>

// ********************************************************************************************************************
// Constants
// ********************************************************************************************************************

// Pin definitions
#define I2C_SCL_PIN             1
#define I2C_SDA_PIN             0

#define TEMP_MEAT_SPI_CS        17
#define TEMP_MEAT_SPI_MOSI      19
#define TEMP_MEAT_SPI_MISO      20
#define TEMP_MEAT_SPI_SCK       18
#define RREF                    4300.0
#define RNOMINAL                1000.0

#define TEMP_MEAT_POWER_PIN     16

#define TEMP_AIR_TOP_POWER_PIN  2
#define TEMP_AIR_BOT_POWER_PIN  3

#define FAN_RELAY_PIN           5
#define FAN_POWER_PIN           4
#define HEATER_RELAY_PIN        22  
#define HEATER_FAN_PIN          14
#define SMOKER_RELAY_PIN        26

// Control parameters
#define FAN_ON_TEMP_DIFF        20  // Temperature difference to turn on fan
#define FAN_OFF_TEMP_DIFF       10  // Temperature difference to turn off fan

// Failsafe Constants
#define MAX_SAFE_TEMP           400  // Maximum safe temperature in Fahrenheit
#define TEMP_READ_TIMEOUT       5000  // Temperature sensor read timeout in milliseconds
#define HEATER_TIMEOUT          30000  // Heater timeout in milliseconds
#define SMOKER_TIMEOUT          30000  // Smoker timeout in milliseconds
#define SMOKER_MIN_CYCLE_TIME   5000   // Minimum smoker cycle time in milliseconds
#define COOKING_TIMEOUT         30000  // Cooking timeout in milliseconds

// MCP9600 I2C addresses
#define TEMP_AIR_TOP_ADDR       0x66
#define TEMP_AIR_BOTTOM_ADDR    0x67

#define LOOP_TIMEOUT             5000  // 5 seconds watchdog timeout for each loop
#define TELEMETRY_INTERVAL       1000
#define SERIAL_FLUSH_INTERVAL   30000

// ********************************************************************************************************************
// Global Variables
// ********************************************************************************************************************

// Temperature readings
int temp_air_top_value          = 0;  // Air temperature at the top of the smoker
int temp_air_bottom_value       = 0;  // Air temperature at the bottom of the smoker
int temp_meat_value             = 0;  // Meat temperature

// State variables
bool cooking_state              = false;  // Cooking/System on/off state
long last_cooking_message_time  = 0;
long last_message_time          = 0;      // Last message time
long startup_time               = 0;      // Startup time
long last_successful_temp_read  = 0;      // Last successful temperature read time
long last_heartbeat             = 0;      // Last heartbeat time
long last_buffer_flush          = 0;      // Last buffer flush time
int consecutive_read_errors     = 0;      // Number of consecutive read errors

// Fan state
bool fan_state                  = false;

// Heater state
bool heater_state               = false;

// Smoker state
bool smoker_state               = false;  // Smoker on/off state
int smoker_rate                 = 0;      // Smoker % on rate/duty cycle
unsigned long smoker_last_toggle_time = 0;      // Last smoker toggle time

// Watchdog tracking variables
long last_loop0_time            = 0;      // Last loop0 time
long last_loop1_time            = 0;      // Last loop1 time

// Temperature sensor objects
Adafruit_MAX31865 temp_meat_1(TEMP_MEAT_SPI_CS, TEMP_MEAT_SPI_MOSI, TEMP_MEAT_SPI_MISO, TEMP_MEAT_SPI_SCK);

Ambient_Resolution ambientRes = RES_ZERO_POINT_0625;
Adafruit_MCP9600 temp_air_top;
Adafruit_MCP9600 temp_air_bottom;

// ********************************************************************************************************************
// Setups
// ********************************************************************************************************************

void setup() {
    Serial.begin(115200);
    while (!Serial) {delay(100);}
    Serial.println("DEBUG: OpenSmoker setup...");

    watchdog_enable(5000, true);
    
    // Initialize loop monitoring
    last_loop0_time = millis();
    last_loop1_time = millis();

    // Initialize I2C
    Wire.setSDA(I2C_SDA_PIN);
    Wire.setSCL(I2C_SCL_PIN);
    Wire.begin();

    // Initialize power pins
    pinMode(TEMP_AIR_TOP_POWER_PIN, OUTPUT);
    pinMode(TEMP_AIR_BOT_POWER_PIN, OUTPUT);
    pinMode(TEMP_MEAT_POWER_PIN, OUTPUT);
    pinMode(FAN_RELAY_PIN, OUTPUT);
    pinMode(HEATER_RELAY_PIN, OUTPUT);
    pinMode(SMOKER_RELAY_PIN, OUTPUT);
    pinMode(HEATER_FAN_PIN, OUTPUT);

    // Set initial pin state
    digitalWrite(TEMP_AIR_TOP_POWER_PIN, HIGH);
    digitalWrite(TEMP_AIR_BOT_POWER_PIN, HIGH);
    digitalWrite(TEMP_MEAT_POWER_PIN, HIGH);
    digitalWrite(HEATER_FAN_PIN, HIGH);

    digitalWrite(FAN_RELAY_PIN, LOW);
    digitalWrite(HEATER_RELAY_PIN, LOW);
    digitalWrite(SMOKER_RELAY_PIN, LOW);
    delay(500);


    // Meat Temp Probe
    temp_meat_1.begin(MAX31865_3WIRE);

    // Air Temp Probes
    if (!temp_air_top.begin(TEMP_AIR_TOP_ADDR)) {
        Serial.println("ERROR: Sensor not found. Check wiring!");
        while (1);
    }
    if (!temp_air_bottom.begin(TEMP_AIR_BOTTOM_ADDR)) {
        Serial.println("ERROR: Sensor not found. Check wiring!");
        while (1);
    }
    
    temp_air_top.setAmbientResolution(ambientRes);
    temp_air_bottom.setAmbientResolution(ambientRes);
    temp_air_top.setADCresolution(MCP9600_ADCRESOLUTION_18);
    temp_air_bottom.setADCresolution(MCP9600_ADCRESOLUTION_18);
    temp_air_top.setThermocoupleType(MCP9600_TYPE_K);
    temp_air_bottom.setThermocoupleType(MCP9600_TYPE_K);
    temp_air_top.setFilterCoefficient(3);
    temp_air_bottom.setFilterCoefficient(3);
    temp_air_top.setAlertTemperature(1, 30);
    temp_air_top.configureAlert(1, true, true);  // alert 1 enabled, rising temp
    temp_air_bottom.setAlertTemperature(1, 30);
    temp_air_bottom.configureAlert(1, true, true);  // alert 1 enabled, rising temp

    temp_air_top.enable(true);
    temp_air_bottom.enable(true);

    Serial.println("DEBUG:OpenSmoker setup complete.");
}


void setup1() {
    while (!Serial) {delay(100);}
    Serial.println("DEBUG: OpenSmoker setup1...");

    delay(1000);
    
    Serial.println("DEBUG: OpenSmoker setup1 complete.");
}

// ********************************************************************************************************************
// Main Loops
// ********************************************************************************************************************

// Loop in charge of reading the temperature sensors and controlling the fan and heater
void loop() {
    // Update the last loop0 time
    last_loop0_time = millis();
    
    // Only pet the watchdog if both loops are running
    if (millis() - last_loop1_time < LOOP_TIMEOUT) {
        watchdog_update();
    } else {
        Serial.println("ERROR: loop1() has failed, not petting watchdog!");
    }

    // Meat Temp Probe
    uint16_t rtd = temp_meat_1.readRTD();
    temp_meat_value = celsius_to_fahrenheit(temp_meat_1.temperature(RNOMINAL, RREF));

    // Check and print any faults with the meat temp probe
    uint8_t fault = temp_meat_1.readFault();
    if (fault) {
        Serial.print("ERROR: Fault 0x"); Serial.println(fault, HEX);
        if (fault & MAX31865_FAULT_HIGHTHRESH) {
            Serial.println("RTD High Threshold"); 
        }
        if (fault & MAX31865_FAULT_LOWTHRESH) {
            Serial.println("RTD Low Threshold"); 
        }
        if (fault & MAX31865_FAULT_REFINLOW) {
            Serial.println("REFIN- > 0.85 x Bias"); 
        }
        if (fault & MAX31865_FAULT_REFINHIGH) {
            Serial.println("REFIN- < 0.85 x Bias - FORCE- open"); 
        }
        if (fault & MAX31865_FAULT_RTDINLOW) {
            Serial.println("RTDIN- < 0.85 x Bias - FORCE- open"); 
        }
        if (fault & MAX31865_FAULT_OVUV) {
            Serial.println("Under/Over voltage"); 
        }
        temp_meat_1.clearFault();
    }

    // Air Temp Probes
    temp_air_top_value = celsius_to_fahrenheit(temp_air_top.readThermocouple());
    temp_air_bottom_value = celsius_to_fahrenheit(temp_air_bottom.readThermocouple());

    last_successful_temp_read = millis();

    // Control the fan
    control_cooking_state();
    control_fan();
    control_heater();
    control_smoker();

    delay(1000);
}


// Loop in charge of receiving serial messages and flushing the serial buffers
void loop1() {
    // Update the last loop1 time
    last_loop1_time = millis();
    
    // Only pet the watchdog if both loops are running
    if (millis() - last_loop0_time < LOOP_TIMEOUT) {
        watchdog_update();
    } else {
        Serial.println("ERROR: loop() has failed, not petting watchdog!");
    }
    
    receive_serial_message();
    
    // Send telemetry data periodically
    if (millis() - last_heartbeat > TELEMETRY_INTERVAL) {
        send_telemetry();
        last_heartbeat = millis();
    }
    
    // Periodically flush serial buffers
    if (millis() - last_buffer_flush > SERIAL_FLUSH_INTERVAL) {
        flush_serial_buffers();
    }
    
    delay(100);
}



// ********************************************************************************************************************
// Functions
// ********************************************************************************************************************


void control_cooking_state() {
    if (last_cooking_message_time + COOKING_TIMEOUT < millis()) {
        cooking_state = false;
    }
}


// Convert Celsius to Fahrenheit and return as integer
int celsius_to_fahrenheit(float celsius) {
    return (int)((celsius * 9.0/5.0) + 32.0);
}


void control_fan() {
    // Check if we have valid temperature readings
    if (isnan(temp_air_top_value) || isnan(temp_air_bottom_value)) {
        Serial.println("ERROR: Invalid temperature readings for fan control");
        digitalWrite(FAN_RELAY_PIN, LOW);
        return;
    }

    if (cooking_state == false) {
        digitalWrite(FAN_RELAY_PIN, LOW);
        fan_state = false;
        return;
    }
    
    if (abs(temp_air_top_value - temp_air_bottom_value) > FAN_ON_TEMP_DIFF) {
        digitalWrite(FAN_RELAY_PIN, HIGH);
        fan_state = true;
    } else if (abs(temp_air_top_value - temp_air_bottom_value) < FAN_OFF_TEMP_DIFF) {
        digitalWrite(FAN_RELAY_PIN, LOW);
        fan_state = false;
    }
}


void control_heater() {
    // Check if we have valid temperature readings
    if (isnan(temp_air_top_value) || isnan(temp_air_bottom_value) || isnan(temp_meat_value)) {
        Serial.println("ERROR: Invalid temperature readings for heater control");
        digitalWrite(HEATER_RELAY_PIN, LOW);
        return;
    }
    
    // Check for maximum safe temperature (already in Fahrenheit)
    if (temp_air_top_value > MAX_SAFE_TEMP || temp_air_bottom_value > MAX_SAFE_TEMP || temp_meat_value > MAX_SAFE_TEMP) {
        Serial.println("ERROR: Maximum safe temperature exceeded, disabling heater.");
        digitalWrite(HEATER_RELAY_PIN, LOW);
        heater_state = false;
        return;
    }
    
    // Check for timeout since last heater command
    if (cooking_state == false) {
        digitalWrite(HEATER_RELAY_PIN, LOW);
        heater_state = false;
        return;
    }
    
    // Check for temperature sensor timeouts
    if (millis() - last_successful_temp_read > TEMP_READ_TIMEOUT) {
        Serial.println("ERROR: Temperature sensor timeout, disabling heater.");
        digitalWrite(HEATER_RELAY_PIN, LOW);
        heater_state = false;
        return;
    }

    // Control the heater
    if (heater_state == true) {
        digitalWrite(HEATER_RELAY_PIN, HIGH);
    } else if (heater_state == false) {
        digitalWrite(HEATER_RELAY_PIN, LOW);
    }
}


void control_smoker() {
    if (cooking_state == false) {
        digitalWrite(SMOKER_RELAY_PIN, LOW);
        smoker_state = false;
        return;
    }

    // Control the smoker based on the rate
    unsigned long current_time = millis();
    unsigned long cycle_position = current_time % SMOKER_MIN_CYCLE_TIME;
    
    // Calculate the on time within the cycle based on the rate percentage
    unsigned long on_time = (SMOKER_MIN_CYCLE_TIME * smoker_rate) / 100;
    
    // If rate is 0, ensure smoker is off
    if (smoker_rate <= 0) {
        digitalWrite(SMOKER_RELAY_PIN, LOW);
        smoker_state = false;
    }
    // If rate is 100 or greater, ensure smoker is on
    else if (smoker_rate >= 100) {
        digitalWrite(SMOKER_RELAY_PIN, HIGH);
        smoker_state = true;
    }
    // Otherwise, implement the duty cycle
    else {
        // If we're in the "on" portion of the cycle
        if (cycle_position < on_time) {
            digitalWrite(SMOKER_RELAY_PIN, HIGH);
            smoker_state = true;
        } 
        // If we're in the "off" portion of the cycle
        else {
            digitalWrite(SMOKER_RELAY_PIN, LOW);
            smoker_state = false;
        }
    }
}

void receive_serial_message() {
    if (Serial.available()) {
        String message = Serial.readStringUntil('\n');
        message.trim();
        Serial.print("DEBUG: Received message: "); Serial.println(message);
        
        // Parse the message
        if (message.startsWith("HEATER_STATE")) {
            // Extract the state from the message
            int state = message.substring(13).toInt();
            if (state == 1) {
                heater_state = true;
            } else if (state == 0) {
                heater_state = false;
            }
            Serial.print("DEBUG: Heater state set to: "); Serial.println(heater_state);
        } else if (message.startsWith("SMOKER_RATE")) {
            // Extract the rate from the message
            int rate = message.substring(12).toInt();
            smoker_rate = rate;
            Serial.print("DEBUG: Smoker rate set to: "); Serial.println(smoker_rate);
        } else if (message.startsWith("COOKING_STATE")) {
            // Extract the state from the message
            int state = message.substring(14).toInt();
            cooking_state = state == 1;
            last_cooking_message_time = millis();
            // Serial.print("DEBUG: Cooking state set to: "); Serial.println(cooking_state);

        }
    }
}


void send_telemetry() {
    // Create JSON document
    StaticJsonDocument<200> doc;
    
    // Add telemetry data
    doc["timestamp"] = millis();
    doc["temp_air_top"] = temp_air_top_value;
    doc["temp_air_bottom"] = temp_air_bottom_value;
    doc["temp_meat"] = temp_meat_value;
    doc["cooking_state"] = cooking_state ? "ON" : "OFF";
    doc["heater_state"] = heater_state ? "ON" : "OFF";
    doc["fan_state"] = fan_state ? "ON" : "OFF";
    doc["smoker_state"] = smoker_state ? "ON" : "OFF";
    doc["smoker_rate"] = smoker_rate;
    
    // Serialize JSON to Serial
    serializeJson(doc, Serial);
    Serial.println();
    
    // Serial.println("DEBUG: Telemetry message sent.");
}


void flush_serial_buffers() {
    // Flush the input buffer
    while (Serial.available() > 0) {
        Serial.read();
    }
    
    // Flush the output buffer
    Serial.flush();
    
    last_buffer_flush = millis();
    Serial.println("DEBUG: Serial buffers flushed.");
}
