/* --------------------------------------------------------------------------------------------------------------------
Arduino program for a Raspberry Pi Pico RP2040
Control unit for an electric meat smoker.
Attached sensors:
- On/off switch. When switch is turned on, enable the heating and fan logic. 
    Connected over GPIO: 1 GPIO input pin needed.
- Rotary encoder with push button for controlling the device and setting temperatures. 
    Connected over GPIO: 3 GPIO input pins needed for rotation detection and button.
- K-type thermocouple connected to a MAX6675 at the top of the enclosure meassuring top temperature. 
    Connected over SPI: DO, CS, CLK pins needed.
- K-type thermocouple connected to a MAX6675 at the bottom of the enclosure measuring bottom temperature. 
    Connected over SPI: DO, CS, CLK pins needed.
- K-type thermocouple connected to a MAX6675 inserted into the meat meassuring internal meat temperature. 
    Connected over SPI: DO, CS, CLK pins needed.
- 120VAC solid state relay controlling the 1200W heating element inside the enclosure. 
    Connected over GPIO: 1 GPIO output pin needed.
- 12VDC mosfet controlling the circulation fan inside the enclosure. 
    Connected over GPIO: 1 GPIO output pin needed.
- 20x4 character LCD that shows information about the smoker. 
    Connected over I2C: SDA and SCL pins needed.

Libraries recommended:
- max6675.h
- Wire.h
- LiquidCrystal_I2C.h

Logic:
- On/off switch:
    Enables and disables the heating and fan functionality of the smoker, essentially the on/off switch.
- Rotary encoder & button controls:
    Push button cycles through different variables to configure: Desired max enclosure temperature and desired meat 
    temperature. When rotary encoder is turned clockwise, it increases the temperature by 2F per click, and when turned
    counter-clockwise, it decreases the temperature by 2F per click.
- Heater element: 
    Turn on for a minimum of 15 seconds, with a cooldown of minimum 15 seconds. Use PWM to trigger relay state.  Turn 
    off once either top or bottom enclosure temperature reaches desired temperature. Turn on again if the enclosure 
    temperature drops 5F below the desired temperature. When the meat temperature has reached the target temperature, 
    set the desired enclosure temperature to the desired meat temperature.  
    Emergency cutoff if any thermocouple detects a temperature above 300F, go into an error state and do not allow the fan or 
    heater element to turn on again until after the on/off switch has been toggled to off then on again to clear the error state.
- Fan: 
    If difference between top and bottom temperatures is greater than 30F, turn fan on for at least 1 minutes. Turn off
    once temperature is within 20F.

Core 0:
- Main heater/fan/temp logic.
- LCD updates.
Core 1:
- Rotary encoder and button.

*/ 

#include <Arduino.h>
#include <Wire.h>
#include <max6675.h>
#include <LiquidCrystal_I2C.h>
#include <FreeRTOS.h>

// Pin Definitions
#define ON_OFF_SWITCH_PIN 2       // GPIO for on/off switch input
#define ENCODER_CLK_PIN   21      // GPIO for rotary encoder clock
#define ENCODER_DT_PIN    20      // GPIO for rotary encoder data
#define ENCODER_BTN_PIN   19      // GPIO for rotary encoder button
#define HEATER_RELAY_PIN  28      // GPIO for heater relay control
#define FAN_CONTROL_PIN   22      // GPIO for fan control
#define LCD_I2C_SDA_PIN   4       // GPIO for LCD I2C
#define LCD_I2C_SCL_PIN   5       // GPIO for LCD I2C

// SPI Pins for MAX6675 Thermocouples
#define THERMO_TOP_CLK      18    // SPI clock
#define THERMO_TOP_CS       17    // Chip select
#define THERMO_TOP_DO       16    // Data out
#define THERMO_TOP_OFFSET   3     // F change to get sensor to 32F on ice water

#define THERMO_BOT_CLK      14    // SPI clock
#define THERMO_BOT_CS       13    // Chip select
#define THERMO_BOT_DO       12    // Data out
#define THERMO_BOT_OFFSET   3     // F change to get sensor to 32F on ice water

#define THERMO_MEAT_CLK     10    // SPI clock
#define THERMO_MEAT_CS      9     // Chip select
#define THERMO_MEAT_DO      8     // Data out
#define THERMO_MEAT_OFFSET  0     // F change to get sensor to 32F on ice water

// Other Parameters
#define EMERGENCY_TEMP      250   // Degree F for emergency shutdown of system
#define FAN_CYCLE_TIME      60000 // ms minimum fan on or off duration
#define FAN_TEMP_DELTA_ON   30    // Degree F difference between probes for fan to turn on
#define FAN_TEMP_DELTA_OFF  15    // Degree F difference between probes for fan to turn off
#define HEATER_CYCLE_TIME   10000 // Minimum time between turning heater SSR on or off

// Initialize MAX6675 instances
MAX6675 thermoTop(THERMO_TOP_CLK, THERMO_TOP_CS, THERMO_TOP_DO);
MAX6675 thermoBot(THERMO_BOT_CLK, THERMO_BOT_CS, THERMO_BOT_DO);
MAX6675 thermoMeat(THERMO_MEAT_CLK, THERMO_MEAT_CS, THERMO_MEAT_DO);

// Initialize LCD (0x27 is the typical I2C address, adjust if needed)
LiquidCrystal_I2C lcd(0x27, 20, 4);

// System States
bool system_on = false;
bool system_on_prev = false;
bool error_state = false;
bool heater_on = false;
bool  fan_on = false;
unsigned long last_heater_toggle_time = 0;
unsigned long last_fan_toggle_time = 0;
unsigned long timer_start_time = 0;

// Temperature Variables
int top_temp = 0;
int bottom_temp = 0;
int meat_temp = 0;
int desired_temp = 230;    // Default target temperature
int desired_meat_temp = 190;// Default target meat temperature
float temp_buffer = 5.0;   // Temperature buffer for heater control

// Rotary Encoder Variables
int encoder_pos = 0;
int encoder_state_last;
int current_setting = 0;   // 0 = enclosure temp, 1 = meat temp
unsigned long last_button_press = 0;
const int button_debounce_time = 500;

/* Function Prototypes */
void updateDisplay();
void controlHeater();
void controlFan();
void handleEncoder();
void handleButton();
String getElapsedTime();

/* ----------------------------------------------------------------------------------------------------------------- */

void setup() {
  // Initialize Serial for debugging
  Serial.begin(115200);
  delay(1000);
  
  // Configure pins
  pinMode(ON_OFF_SWITCH_PIN, INPUT_PULLUP);
  pinMode(ENCODER_CLK_PIN, INPUT);
  pinMode(ENCODER_DT_PIN, INPUT);
  pinMode(ENCODER_BTN_PIN, INPUT_PULLUP);
  pinMode(HEATER_RELAY_PIN, OUTPUT);
  pinMode(FAN_CONTROL_PIN, OUTPUT);
  
  // Initialize outputs to safe state
  digitalWrite(HEATER_RELAY_PIN, LOW);
  digitalWrite(FAN_CONTROL_PIN, LOW);
  
  // Initialize LCD
  Wire.setSDA(LCD_I2C_SDA_PIN);
  Wire.setSCL(LCD_I2C_SCL_PIN);
  Wire.begin();
  lcd.init();
  lcd.backlight();
  
  // Get initial encoder state
  encoder_state_last = digitalRead(ENCODER_CLK_PIN);
  
  // Initial LCD display
  updateDisplay();
}


void setup1() {

}

/* ----------------------------------------------------------------------------------------------------------------- */


void loop() {
  // Read system state
  system_on = !digitalRead(ON_OFF_SWITCH_PIN);
  Serial.print("systemOn = "); Serial.println(system_on);

  // Reset time when turned on
  if(system_on != system_on_prev) {
    if(system_on) {
      timer_start_time = millis();
    }
    system_on_prev = system_on;
  }
  
  // Read temperatures
  top_temp    = (int)thermoTop.readFahrenheit() + THERMO_TOP_OFFSET;
  bottom_temp = (int)thermoBot.readFahrenheit() + THERMO_BOT_OFFSET;
  meat_temp   = (int)thermoMeat.readFahrenheit() + THERMO_MEAT_OFFSET;

  if (top_temp > 999) top_temp = 999;
  if (bottom_temp > 999) bottom_temp = 999;
  if (meat_temp > 999) meat_temp = 999;
  
  // Check for emergency temperature condition
  if (top_temp >= EMERGENCY_TEMP || bottom_temp >= EMERGENCY_TEMP || meat_temp >= EMERGENCY_TEMP) {
    error_state = true;
    system_on = false;
  }
  
  // Control logic only when system is on and not in error state
  if (system_on && !error_state) {
    // Heater control logic
    controlHeater();
    
    // Fan control logic
    controlFan();
  } else {
    // System off or error state - ensure everything is off
    digitalWrite(HEATER_RELAY_PIN, LOW);
    digitalWrite(FAN_CONTROL_PIN, LOW);
    heater_on = false;
    fan_on = false;
  }
  
  // Update display
  updateDisplay();

  // Small delay to prevent excessive CPU usage
  delay(100);
}


void loop1() {
  // Handle rotary encoder
  handleEncoder();

  // Handle button press
  handleButton();

  delay(5);
}

/* ----------------------------------------------------------------------------------------------------------------- */


void handleEncoder() {
  int currentState = digitalRead(ENCODER_CLK_PIN);
  
  if (currentState != encoder_state_last && currentState == 1) {
    if (digitalRead(ENCODER_DT_PIN) != currentState) {
      // Clockwise rotation
      if (current_setting == 0) {
        desired_temp += 2;
      } else {
        desired_meat_temp += 2;
      }
    } else {
      // Counter-clockwise rotation
      if (current_setting == 0) {
        desired_temp -= 2;
      } else {
        desired_meat_temp -= 2;
      }
    }
  }
  encoder_state_last = currentState;
}

void handleButton() {
  if (digitalRead(ENCODER_BTN_PIN) == LOW && (millis() - last_button_press) > button_debounce_time) {
    current_setting = (current_setting + 1) % 2;  // Toggle between 0 and 1
    last_button_press = millis();
  }
}

void controlHeater() {
  unsigned long current_time = millis();
  
  // Check if meat has reached target temperature
  if (meat_temp >= desired_meat_temp) {
    desired_temp = desired_meat_temp;  // Maintain meat temperature
  }
  
  // Heater control with minimum on/off times
  if (!heater_on && (top_temp < (desired_temp - temp_buffer)) && (current_time - last_heater_toggle_time >= HEATER_CYCLE_TIME)) {
    digitalWrite(HEATER_RELAY_PIN, HIGH);
    heater_on = true;
    last_heater_toggle_time = current_time;
  } else if (heater_on && ((top_temp >= desired_temp) || (bottom_temp >= desired_temp)) && 
             (current_time - last_heater_toggle_time >= HEATER_CYCLE_TIME)) {
    digitalWrite(HEATER_RELAY_PIN, LOW);
    heater_on = false;
    last_heater_toggle_time = current_time;
  }
}


void controlFan() {
  unsigned long current_time = millis();
  float temp_difference = abs(top_temp - bottom_temp);
  
  // Fan control with minimum run time
  if (!fan_on && (temp_difference > FAN_TEMP_DELTA_ON) && 
      (current_time - last_fan_toggle_time >= FAN_CYCLE_TIME)) {
    digitalWrite(FAN_CONTROL_PIN, HIGH);
    fan_on = true;
    last_fan_toggle_time = current_time;
  } else if (fan_on && (temp_difference <= FAN_TEMP_DELTA_OFF) && 
             (current_time - last_fan_toggle_time >= FAN_CYCLE_TIME)) {
    digitalWrite(FAN_CONTROL_PIN, LOW);
    fan_on = false;
    last_fan_toggle_time = current_time;
  }
}

void updateDisplay() {
  // Row 1
  String title_text = String("Smokey! ");
  if(!error_state && system_on) {
    title_text += "   " + getElapsedTime();
  } else if(!system_on) {
    title_text += "            ";
  }

  // Row 2
  String air_text = String("Air : ");
  if(bottom_temp < 100) {air_text += String(" ");}
  air_text += String(bottom_temp);
  air_text += String("-");
  if(top_temp < 100) {air_text += String(" ");}
  air_text += String(top_temp);
  air_text += String(" ->");
  if(current_setting == 0) {air_text += String("*");} else {air_text += String(" ");}
  if(desired_temp < 100) {air_text += String(" ");}
  air_text += String(desired_temp);

  // Row 3
  String meat_text = String("Meat:     ");
  if(meat_temp < 10) {meat_text += String("  ");}
  else if(meat_temp < 100) {meat_text += String(" ");}
  meat_text += String(meat_temp);
  meat_text += String(" ->");
  if(current_setting == 1) {meat_text += String("*");} else {meat_text += String(" ");}
  meat_text += String(desired_meat_temp);
  
  // Row 4
  String status_text = String("");
  if(error_state) {
    status_text += String("ERROR: HIGH TEMP!!!!");
  } else if(!system_on) {
    status_text += String("System: OFF");
  } else {
    status_text += String("H:");
    status_text += String(heater_on ? "ON " : "OFF");
    status_text += String(" F:");
    status_text += String(fan_on ? "ON " : "OFF");
  }
  if(status_text.length() < 20) {
    int spacesToAdd = 20 - status_text.length();
    for (int i = 0; i < spacesToAdd; i++) {
      status_text += " ";
    }
  }

  lcd.setCursor(0, 0);
  lcd.print(title_text);
  lcd.setCursor(0, 1);
  lcd.print(air_text);
  lcd.setCursor(0, 2);
  lcd.print(meat_text);
  lcd.setCursor(0, 3);
  lcd.print(status_text);

}


String getElapsedTime() {
  unsigned long current_time = millis();
  unsigned long elapsed_time = current_time - timer_start_time;

  // Convert milliseconds to hours, minutes, seconds
  int hours = elapsed_time / 3600000;
  int minutes = (elapsed_time % 3600000) / 60000;
  int seconds = (elapsed_time % 60000) / 1000;

  // Format the time as HH:MM:SS using String
  String time_string = "";
  if (hours < 10) time_string += "0";
  time_string += String(hours) + "h";
  if (minutes < 10) time_string += "0";
  time_string += String(minutes) + "m";
  if (seconds < 10) time_string += "0";
  time_string += String(seconds) + "s";

  return time_string;
}