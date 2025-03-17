#######################################################################################################################
# OpenSmoker
#######################################################################################################################

# Author: Constantine Vavourakis
# Date: 2025-03-14

# Copyright (C) 2025 

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#######################################################################################################################
# Imports
#######################################################################################################################
print("Importing modules...")
import _thread
from max6675 import MAX6675
from machine import Pin, I2C
from i2c_lcd import I2cLcd
import time
import network
import secrets

####################################################################################################################### 
# Constants
#######################################################################################################################
print("Defining constants...")
# LCD
LCD_I2C_ADDR            = 0x27
LCD_NUM_COLS            = 20
LCD_NUM_ROWS            = 4
LCD_I2C_SDA_PIN         = 4
LCD_I2C_SCL_PIN         = 5

# Buttons
BUTTON_INCREASE_PIN     = 22    # Increase button pin
BUTTON_MENU_PIN         = 26    # Menu button pin
BUTTON_DECREASE_PIN     = 27    # Decrease button pin
BUTTON_DEBOUNCE_TIME    = 50    # Debounce time in milliseconds
BUTTON_HOLD_TIME        = 1000  # Time in milliseconds to consider a button held
BUTTON_REPEAT_RATE      = 100   # Time in milliseconds between repeats when held (faster)
BUTTON_REPEAT_STEP      = 5     # Amount to change per repeat when button is held

# Thermocouple pins
TEMP_AIR_TOP_DO_PIN     = 12
TEMP_AIR_TOP_CS_PIN     = 13
TEMP_AIR_TOP_SCK_PIN    = 14
TEMP_AIR_TOP_VCC_PIN    = 15

TEMP_AIR_BOTTOM_DO_PIN  = 16
TEMP_AIR_BOTTOM_CS_PIN  = 17
TEMP_AIR_BOTTOM_SCK_PIN = 18
TEMP_AIR_BOTTOM_VCC_PIN = 19

TEMP_MEAT_1_DO_PIN      = 8
TEMP_MEAT_1_CS_PIN      = 9
TEMP_MEAT_1_SCK_PIN     = 10
TEMP_MEAT_1_VCC_PIN     = 11

# On/Off switch
ON_OFF_GPIO_PIN         = 2
ON_OFF_VCC_PIN          = 3

# Relays
HEATER_RELAY_PIN        = 7         # Heater relay pin
FAN_RELAY_PIN           = 6         # Fan relay pin
MIN_CYCLE_TIME          = 5         # Minimum cycle time in seconds

# PID controller constants
PID_P                   = 2.0       # Proportional gain
PID_I                   = 0.1       # Integral gain
PID_D                   = 1.0       # Derivative gain

# Temperature averaging constants
TEMP_HISTORY_SIZE       = 5       # Number of readings to average
TEMP_AIR_TARGET_MIN     = 150     # Minimum air target temperature
TEMP_AIR_TARGET_MAX     = 300     # Maximum air target temperature
TEMP_MEAT_1_TARGET_MIN  = 120     # Minimum meat target temperature
TEMP_MEAT_1_TARGET_MAX  = 210     # Maximum meat target temperature

#######################################################################################################################
# Variables & GPIO
#######################################################################################################################
print("Defining variables...")

# Temperatures
temp_air_top        = 100
temp_air_bottom     = 100
temp_air_target     = 225
temp_meat_1         = 100
temp_meat_1_target  = 190

# Temperature history arrays for averaging
temp_air_top_history    = [100] * TEMP_HISTORY_SIZE
temp_air_bottom_history = [100] * TEMP_HISTORY_SIZE
temp_meat_1_history     = [100] * TEMP_HISTORY_SIZE

# Buttons
button_pressed      = False
current_button      = False
button_selection    = 'air'
button_menu         = Pin(BUTTON_MENU_PIN, Pin.IN, Pin.PULL_UP)
button_increase     = Pin(BUTTON_INCREASE_PIN, Pin.IN, Pin.PULL_UP)
button_decrease     = Pin(BUTTON_DECREASE_PIN, Pin.IN, Pin.PULL_UP)

# WiFi
wifi_status         = "Disconnected"
current_wifi_status = "Disconnected"

# System
system_on           = False
system_on_time      = 0
system_run_time     = 0

# PID controller
pid_error_sum       = 0.0
pid_last_error      = 0.0
pid_last_time       = 0
heater_state        = False
heater_last_change_time = 0

# On/Off switch
on_off_pin          = Pin(ON_OFF_GPIO_PIN, Pin.IN, Pin.PULL_UP)
on_off_vcc_pin      = Pin(ON_OFF_VCC_PIN, Pin.OUT)

# Relays
heater_relay        = Pin(HEATER_RELAY_PIN, Pin.OUT)
fan_relay           = Pin(FAN_RELAY_PIN, Pin.OUT)

# Thermocouples
temp_air_top_sck    = Pin(TEMP_AIR_TOP_SCK_PIN, Pin.OUT)
temp_air_top_cs     = Pin(TEMP_AIR_TOP_CS_PIN, Pin.OUT)
temp_air_top_do     = Pin(TEMP_AIR_TOP_DO_PIN, Pin.IN)
temp_air_top_vcc    = Pin(TEMP_AIR_TOP_VCC_PIN, Pin.OUT)

temp_air_bottom_sck = Pin(TEMP_AIR_BOTTOM_SCK_PIN, Pin.OUT)
temp_air_bottom_cs  = Pin(TEMP_AIR_BOTTOM_CS_PIN, Pin.OUT)
temp_air_bottom_do  = Pin(TEMP_AIR_BOTTOM_DO_PIN, Pin.IN)
temp_air_bottom_vcc = Pin(TEMP_AIR_BOTTOM_VCC_PIN, Pin.OUT)

temp_meat_1_sck     = Pin(TEMP_MEAT_1_SCK_PIN, Pin.OUT)
temp_meat_1_cs      = Pin(TEMP_MEAT_1_CS_PIN, Pin.OUT)
temp_meat_1_do      = Pin(TEMP_MEAT_1_DO_PIN, Pin.IN)
temp_meat_1_vcc     = Pin(TEMP_MEAT_1_VCC_PIN, Pin.OUT)

# Locks for thread-safe access to shared data
temp_lock           = _thread.allocate_lock()
button_lock         = _thread.allocate_lock()
heater_lock         = _thread.allocate_lock()

#######################################################################################################################
# Initialization
#######################################################################################################################
print("Initializing...")

# Power
on_off_vcc_pin.value(1)        # Turn on power to on/off switch
temp_air_top_vcc.value(1)      # Turn on power to thermocouple
temp_air_bottom_vcc.value(1)   # Turn on power to thermocouple
temp_meat_1_vcc.value(1)       # Turn on power to thermocouple
heater_relay.value(0)          # Initialize heater to OFF
fan_relay.value(0)             # Initialize fan to OFF

# Thermocouples
temp_air_top_sensor     = MAX6675(temp_air_top_sck, temp_air_top_cs, temp_air_top_do)
temp_air_bottom_sensor  = MAX6675(temp_air_bottom_sck, temp_air_bottom_cs, temp_air_bottom_do)
temp_meat_1_sensor      = MAX6675(temp_meat_1_sck, temp_meat_1_cs, temp_meat_1_do)

# LCD
i2c_lcd = I2C(0, sda=Pin(LCD_I2C_SDA_PIN), scl=Pin(LCD_I2C_SCL_PIN), freq=400000)
lcd = I2cLcd(i2c_lcd, LCD_I2C_ADDR, LCD_NUM_ROWS, LCD_NUM_COLS)

# print("Initializing Wi-Fi interface...")
# # Init Wi-Fi interface
# wlan = network.WLAN(network.STA_IF)
# wlan.active(True)
# time.sleep(5)

# # Scan for Wi-Fi networks
# networks = wlan.scan()

# # Print Wi-Fi networks
# print("Available WiFi Networks:")
# for network_info in networks:
#     print(network_info)

# # Connect to your network
# wlan.connect(secrets.WIFI_NETWORKS[0][0], secrets.WIFI_NETWORKS[0][1])

# # Wait for Wi-Fi connection
# connection_timeout = 10
# while connection_timeout > 0:
#     if wlan.status() >= 3:
#         break
#     connection_timeout -= 1
#     print('Waiting for Wi-Fi connection...')
#     time.sleep(1)

# # Check if connection is successful
# if wlan.status() != 3:
#     raise RuntimeError('Failed to establish a network connection')
# else:
#     print('Connection successful!')
#     network_info = wlan.ifconfig()
#     print('IP address:', network_info[0])

# print("Wi-Fi initialized")


#######################################################################################################################
# Functions & Tasks
#######################################################################################################################
print("Defining functions and tasks...")

# Function to convert Celsius to Fahrenheit
def celsius_to_fahrenheit(celsius):
    return int((celsius * 9/5) + 32)


# Function to format time in HH:MM:SS
def format_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# Function to calculate average of a list
def calculate_average(values):
    return sum(values) // len(values)


# Function to update temperature history and calculate average
def update_temp_history(history, new_value):
    # Shift all values to the left and add new value at the end
    for i in range(len(history) - 1):
        history[i] = history[i + 1]
    history[-1] = new_value
    
    # Calculate and return the average
    return calculate_average(history)


# # Function to update WiFi status for display
# def update_wifi_status():
#     global wifi_status
    
#     if wlan.isconnected():
#         wifi_status = "Connected"
#     else:
#         wifi_status = "Disconnected"


def read_temps():
    global temp_air_top, temp_air_bottom, temp_meat_1
    global temp_air_top_history, temp_air_bottom_history, temp_meat_1_history
    
    # Read raw temperatures in Celsius and convert to Fahrenheit
    raw_temp_air_top = celsius_to_fahrenheit(int(temp_air_top_sensor.read()))
    raw_temp_air_bottom = celsius_to_fahrenheit(int(temp_air_bottom_sensor.read()))
    raw_temp_meat_1 = celsius_to_fahrenheit(int(temp_meat_1_sensor.read()))

    # limit temps to 999, happens when thermocouple is disconnected
    if raw_temp_air_top > 999:
        raw_temp_air_top = 999
    if raw_temp_air_bottom > 999:
        raw_temp_air_bottom = 999
    if raw_temp_meat_1 > 999:
        raw_temp_meat_1 = 999
    
    # Update temperature histories and calculate averages
    with temp_lock:
        temp_air_top = update_temp_history(temp_air_top_history, raw_temp_air_top)
        temp_air_bottom = update_temp_history(temp_air_bottom_history, raw_temp_air_bottom)
        temp_meat_1 = update_temp_history(temp_meat_1_history, raw_temp_meat_1)
    

def update_lcd():
    global current_encoder, current_button, current_wifi_status, temp_air_bottom, temp_air_top, temp_air_target, temp_meat_1, temp_meat_1_target, system_run_time
    # lcd.clear()
    lcd.move_to(0, 0)  # Move to first line
    # Line 1 - Show timer if system is on, otherwise show OpenSmoker
    if system_on:
        timer_str = format_time(system_run_time)
        lcd.putstr(f"Timer: {timer_str}     ")
    else:
        lcd.putstr(f"OpenSmoker          ")
    
    lcd.move_to(0, 1)  # Move to second line
    # Line 2
    # Space out text to 20 characters
    line_2 = "Air:  "
    if len(str(temp_air_bottom)) < 3:
        line_2 += ' ' + str(temp_air_bottom)
    else:
        line_2 += str(temp_air_bottom)
    line_2 += '-'
    if len(str(temp_air_top)) < 3:
        line_2 += ' ' + str(temp_air_top)
    else:
        line_2 += str(temp_air_top)
    line_2 += ' > ' + str(temp_air_target)
    if button_selection == 'air':
        line_2 += '*'
    else:
        line_2 += ' '

    lcd.putstr(line_2)
    
    lcd.move_to(0, 2)  # Move to third line
    # Line 3
    line_3 = "Meat: "
    if len(str(temp_meat_1)) < 3:
        line_3 += ' ' + str(temp_meat_1)
    else:
        line_3 += str(temp_meat_1)
    line_3 += '     > ' + str(temp_meat_1_target)
    if button_selection == 'meat':
        line_3 += '*'
    else:
        line_3 += ' '
    lcd.putstr(line_3)
    
    lcd.move_to(0, 3)  # Move to fourth line
    # Line 4
    line_4 = "Sys: "
    if system_on:
        line_4 += "ON  "
    else:
        line_4 += "OFF "
    line_4 += "H: "
    if heater_state:
        line_4 += "ON  "
    else:
        line_4 += "OFF "
    line_4 += "W: "
    if wifi_status == "Connected":
        line_4 += "C"
    else:
        line_4 += "D"
    lcd.putstr(line_4)


# Function to read the on/off switch
def read_on_off_switch():
    global system_on, system_on_time
    
    # Get current state
    current_state = not on_off_pin.value()
    
    # Check if system is being turned on
    if current_state and not system_on:
        # System is being turned on, reset timer
        system_on_time = time.time()
    
    # Update system state
    system_on = current_state


# PID controller function for heater
def control_heater():
    global temp_air_top, temp_air_target, temp_meat_1, temp_meat_1_target
    global pid_error_sum, pid_last_error, pid_last_time, heater_last_change_time, heater_state, system_on
    
    # Check if system is on
    if not system_on:
        # Turn off heater if system is off
        with heater_lock:
            heater_relay.value(0)
            heater_state = False
        return
    
    # Check if meat has reached target temperature
    if temp_meat_1 >= temp_meat_1_target:
        # Set air target to meat target to maintain temperature
        temp_air_target = temp_meat_1_target
    
    current_time = time.time()
    
    # Calculate time delta
    if pid_last_time == 0:
        dt = 1.0  # First run, assume 1 second
    else:
        dt = current_time - pid_last_time
    
    # Ensure dt is not too small to avoid division by zero
    if dt < 0.01:
        dt = 0.01
    
    # Calculate error (difference between target and current temperature)
    error = temp_air_target - temp_air_top
    
    # Calculate PID components
    p_term = PID_P * error
    
    # Update integral term with anti-windup (limit accumulation)
    pid_error_sum += error * dt
    if pid_error_sum > 100:
        pid_error_sum = 100
    elif pid_error_sum < -100:
        pid_error_sum = -100
    i_term = PID_I * pid_error_sum
    
    # Calculate derivative term
    d_term = 0
    if dt > 0:
        d_term = PID_D * (error - pid_last_error) / dt
    
    # Calculate PID output
    pid_output = p_term + i_term + d_term
    
    # Determine if heater should be on or off based on PID output
    new_heater_state = pid_output > 0
    
    # Check if enough time has passed since last relay state change
    time_since_last_change = current_time - heater_last_change_time
    
    # Only change relay state if minimum cycle time has passed
    if time_since_last_change >= MIN_CYCLE_TIME:
        if new_heater_state != heater_state:
            with heater_lock:
                heater_relay.value(1 if new_heater_state else 0)
                heater_state = new_heater_state
                heater_last_change_time = current_time
    
    # Update last values for next iteration
    pid_last_error = error
    pid_last_time = current_time


# Function to handle button presses and adjust target temperatures
def button_task():
    global button_selection, temp_air_target, temp_meat_1_target
    
    # Button state variables
    menu_pressed = False
    increase_pressed = False
    decrease_pressed = False
    
    # Button timing variables
    menu_last_press_time = 0
    increase_last_press_time = 0
    decrease_last_press_time = 0
    
    # Button hold timing variables
    increase_hold_start_time = 0
    decrease_hold_start_time = 0
    increase_last_repeat_time = 0
    decrease_last_repeat_time = 0
    
    # Button hold state
    increase_held = False
    decrease_held = False
    
    while True:
        try:
            # Get current time in milliseconds
            current_time = int(time.time() * 1000)
            
            # Read button states (buttons are active low with pull-up)
            menu_current = not button_menu.value()
            increase_current = not button_increase.value()
            decrease_current = not button_decrease.value()
            
            # Handle menu button (with debounce)
            if menu_current and not menu_pressed and (current_time - menu_last_press_time) > BUTTON_DEBOUNCE_TIME:
                # Menu button pressed - toggle between air and meat target
                with button_lock:
                    button_selection = 'meat' if button_selection == 'air' else 'air'
                print(f"Menu button pressed, selection: {button_selection}")
                menu_last_press_time = current_time
            menu_pressed = menu_current
            
            # Handle increase button
            if increase_current:
                if not increase_pressed and (current_time - increase_last_press_time) > BUTTON_DEBOUNCE_TIME:
                    # Initial press
                    increase_pressed = True
                    increase_last_press_time = current_time
                    increase_hold_start_time = current_time
                    
                    # Increment the selected target by 1 on initial press
                    with button_lock:
                        if button_selection == 'air':
                            temp_air_target += 1
                            print(f"Increased air target to {temp_air_target}")
                        else:
                            temp_meat_1_target += 1
                            print(f"Increased meat target to {temp_meat_1_target}")
                
                # Check for hold
                elif increase_pressed and not increase_held and (current_time - increase_hold_start_time) > BUTTON_HOLD_TIME:
                    # Button is being held
                    increase_held = True
                    increase_last_repeat_time = current_time
                    print("Increase button held")
                
                # Handle repeating while held
                elif increase_held and (current_time - increase_last_repeat_time) > BUTTON_REPEAT_RATE:
                    # Increment the selected target at repeat rate with larger step
                    with button_lock:
                        if button_selection == 'air':
                            temp_air_target += BUTTON_REPEAT_STEP
                            print(f"Increased air target to {temp_air_target}")
                        else:
                            temp_meat_1_target += BUTTON_REPEAT_STEP
                            print(f"Increased meat target to {temp_meat_1_target}")
                    increase_last_repeat_time = current_time
            else:
                # Button released
                increase_pressed = False
                increase_held = False
            
            # Handle decrease button
            if decrease_current:
                if not decrease_pressed and (current_time - decrease_last_press_time) > BUTTON_DEBOUNCE_TIME:
                    # Initial press
                    decrease_pressed = True
                    decrease_last_press_time = current_time
                    decrease_hold_start_time = current_time
                    
                    # Decrement the selected target by 1 on initial press
                    with button_lock:
                        if button_selection == 'air':
                            temp_air_target -= 1
                            print(f"Decreased air target to {temp_air_target}")
                        else:
                            temp_meat_1_target -= 1
                            print(f"Decreased meat target to {temp_meat_1_target}")
                
                # Check for hold
                elif decrease_pressed and not decrease_held and (current_time - decrease_hold_start_time) > BUTTON_HOLD_TIME:
                    # Button is being held
                    decrease_held = True
                    decrease_last_repeat_time = current_time
                    print("Decrease button held")
                
                # Handle repeating while held
                elif decrease_held and (current_time - decrease_last_repeat_time) > BUTTON_REPEAT_RATE:
                    # Decrement the selected target at repeat rate with larger step
                    with button_lock:
                        if button_selection == 'air':
                            temp_air_target -= BUTTON_REPEAT_STEP
                            print(f"Decreased air target to {temp_air_target}")
                        else:
                            temp_meat_1_target -= BUTTON_REPEAT_STEP
                            print(f"Decreased meat target to {temp_meat_1_target}")
                    decrease_last_repeat_time = current_time
            else:
                # Button released
                decrease_pressed = False
                decrease_held = False
            
            # Ensure target temperatures stay within reasonable ranges
            with button_lock:
                # Air temperature range (150°F to 350°F)
                if temp_air_target < TEMP_AIR_TARGET_MIN:
                    temp_air_target = TEMP_AIR_TARGET_MIN
                elif temp_air_target > TEMP_AIR_TARGET_MAX:
                    temp_air_target = TEMP_AIR_TARGET_MAX
                
                # Meat temperature range (120°F to 210°F)
                if temp_meat_1_target < TEMP_MEAT_1_TARGET_MIN:
                    temp_meat_1_target = TEMP_MEAT_1_TARGET_MIN
                elif temp_meat_1_target > TEMP_MEAT_1_TARGET_MAX:
                    temp_meat_1_target = TEMP_MEAT_1_TARGET_MAX
            
        except Exception as e:
            print(f"Error in button task: {e}")
        
        # Small delay to prevent hogging the CPU
        time.sleep(0.05)


#######################################################################################################################
# Main Task
#######################################################################################################################
print("Defining main task...")

# Function to run on core 0 (main thread) - handling thermocouple, LCD, and WiFi
def main_task():
    global temperature, encoder_value, button_pressed, wifi_status, current_encoder, current_button, current_wifi_status, system_run_time, system_on_time
    
    # Turn on fan when system is on
    fan_relay.value(1)
    
    # Main loop
    while True:
        try:
            read_temps()
            read_on_off_switch()
            
            # Update run time if system is on
            if system_on:
                system_run_time = int(time.time() - system_on_time)
            
            # Control heater based on PID
            control_heater()

            # # Update WiFi status
            # update_wifi_status()
            # with wifi_lock:
            #     current_wifi_status = wifi_status
                
            update_lcd()
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            
        time.sleep(0.1)

#######################################################################################################################
# Start Core 1 Tasks
#######################################################################################################################
print("Starting tasks on core 1...")

# Start button handling task on core 1
_thread.start_new_thread(button_task, ())

# Wait a moment for the button task to initialize
time.sleep(1)

#######################################################################################################################
# Start Core 0 Main Tasks
#######################################################################################################################
print("Starting main task on core 0...")
main_task()
