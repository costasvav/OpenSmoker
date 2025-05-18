#######################################################################################################################
# Open Smoker Pi
#######################################################################################################################
#
# Author: Constantine Vavourakis
# Date: 2025-03-14
#
# Copyright (C) 2025 
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#######################################################################################################################
# Description
#######################################################################################################################
#
# The OpenSmoker Python script that communicates with the microcontroller.
# 
# Purpose:
# - Control the smoker hardware through the microcontroller over USB-Serial.
# - Write current telemetry and settings to the backend InfluxDB datastore.
# - Locally load/save settings for power failure recovery.
#
#######################################################################################################################
# Imports
#######################################################################################################################
# Set up logging
import logging
import logging.handlers

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.handlers.RotatingFileHandler("opensmoker.log", maxBytes=1000000, backupCount=5), logging.StreamHandler()]
)
logger = logging.getLogger("OpenSmoker")

logger.info("Importing modules...")

import time
import sys
import os
import json
import Smoker_Secrets
import influxdb_client
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import serial


####################################################################################################################### 
# Constants
#######################################################################################################################
logger.info("Defining constants...")

# Serial port for Pi Pico
# SERIAL_PORT         = '/dev/pico_controller'
SERIAL_PORT       = '/dev/ttyACM0'
SERIAL_BAUD         = 115200
PICO_RECONNECT_INTERVAL = 3

# File paths
PARAMS_FILE = "/home/user/OpenSmoker_Parameters.json"
SAVE_INTERVAL = 10  # Save parameters every 10 seconds
MAX_PARAM_AGE = 7200  # Maximum age of saved parameters in seconds (2 hours)

# Last saved parameters
last_saved_params = {
    "temp_air_target": None,
    "temp_meat_1_target": None,
    "cooking_on": None,
    "smoker_rate": None,
    "timestamp": None
}

INFLUXDB_RECONNECT_INTERVAL = 5  # Reconnect every 5 seconds if connection is lost
INFLUX_WRITE_INTERVAL = 5  # Write to InfluxDB every 5 seconds

#######################################################################################################################
# Functions
#######################################################################################################################
logger.info("Defining functions and tasks...")


# Heating element control
def control_heater():
    global temp_air_top, temp_air_bottom, heater_state, serial_connected

    if not serial_connected:
        return  # Skip control if not connected to serial

    if cooking_state:
        avg_temp = (temp_air_top + temp_air_bottom) / 2
        if avg_temp < temp_air_target:
            heater_state = True
            send_command_to_pico('HEATER_STATE 1\n')
        else:
            heater_state = False
            send_command_to_pico('HEATER_STATE 0\n')
    else:
        heater_state = False
        send_command_to_pico('HEATER_STATE 0\n')


#######################################################################################################################
# Functions for parameter saving and loading
#######################################################################################################################

def parameters_changed():
    """Check if any parameters have changed since last save"""
    global temp_air_target, temp_meat_1_target, cooking_state, smoker_rate, last_saved_params
    
    return (
        last_saved_params["temp_air_target"] != temp_air_target or
        last_saved_params["temp_meat_1_target"] != temp_meat_1_target or
        last_saved_params["cooking_on"] != cooking_state or
        last_saved_params["smoker_rate"] != smoker_rate
    )

def check_params_file_updated():
    """Check if parameters file has been modified by another program like the WebApp"""
    global last_params_file_timestamp
    
    try:
        # Get current file modification time
        if os.path.exists(PARAMS_FILE):
            current_timestamp = os.path.getmtime(PARAMS_FILE)
            
            # Check if file has been modified since last check
            if current_timestamp > last_params_file_timestamp:
                logger.info(f"Parameters file was modified externally (last: {last_params_file_timestamp}, current: {current_timestamp})")
                last_params_file_timestamp = current_timestamp
                return True
        else:
            # If file doesn't exist, update timestamp to current time
            last_params_file_timestamp = time.time()
        
        return False
    except Exception as e:
        logger.error(f"Error checking parameter file timestamp: {e}")
        return False

def save_parameters():
    """Save current parameters to JSON file"""
    global temp_air_target, temp_meat_1_target, cooking_state, smoker_rate, last_saved_params, last_params_file_timestamp
    
    # Only save if parameters have changed
    if not parameters_changed():
        return
        
    params = {
        "temp_air_target": temp_air_target,
        "temp_meat_1_target": temp_meat_1_target,
        "cooking_on": cooking_state,
        "smoker_rate": smoker_rate,
        "timestamp": time.time()  # Add current timestamp
    }
    
    try:
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f)
        # Update last saved parameters
        last_saved_params = params.copy()
        # Update file modification timestamp
        last_params_file_timestamp = os.path.getmtime(PARAMS_FILE)
        logger.info("Parameters saved successfully")
    except Exception as e:
        logger.error(f"Error saving parameters: {e}")


def load_parameters():
    """Load parameters from JSON file if it exists and is not older than MAX_PARAM_AGE"""
    global temp_air_target, temp_meat_1_target, cooking_state, smoker_rate, last_saved_params, last_params_file_timestamp
    
    try:
        with open(PARAMS_FILE, 'r') as f:
            params = json.load(f)
            
            # Check if parameters are too old
            saved_timestamp = params.get("timestamp")
            if saved_timestamp is None or (time.time() - saved_timestamp) > MAX_PARAM_AGE:
                logger.info("Saved parameters are too old or missing timestamp, using defaults")
                # Initialize last saved parameters with defaults
                last_saved_params = {
                    "temp_air_target": temp_air_target,
                    "temp_meat_1_target": temp_meat_1_target,
                    "cooking_on": cooking_state,
                    "smoker_rate": smoker_rate,
                    "timestamp": time.time()
                }
                return
                
            # Store previous cooking state to detect changes
            previous_cooking_state = cooking_state
            
            # Load parameters if they're not too old
            temp_air_target = int(params.get("temp_air_target", temp_air_target))
            temp_meat_1_target = int(params.get("temp_meat_1_target", temp_meat_1_target))
            cooking_state = bool(params.get("cooking_on", cooking_state))
            
            # Load smoker rate if available
            if "smoker_rate" in params:
                smoker_rate = int(params.get("smoker_rate", smoker_rate))
                
            # Update last saved parameters
            last_saved_params = {
                "temp_air_target": temp_air_target,
                "temp_meat_1_target": temp_meat_1_target,
                "cooking_on": cooking_state,
                "smoker_rate": smoker_rate,
                "timestamp": saved_timestamp
            }
            
            # If cooking state has changed, send immediate update to Pico
            if previous_cooking_state != cooking_state and serial_connected:
                cooking_state_cmd = 1 if cooking_state else 0
                send_command_to_pico(f'COOKING_STATE {cooking_state_cmd}\n')
                logger.info(f"Sent cooking state update to Pico: {cooking_state}")
            
        # Update file modification timestamp
        last_params_file_timestamp = os.path.getmtime(PARAMS_FILE)
        logger.info("Parameters loaded successfully")
    except FileNotFoundError:
        logger.info("No saved parameters found, using defaults")
        # Initialize last saved parameters with defaults
        last_saved_params = {
            "temp_air_target": temp_air_target,
            "temp_meat_1_target": temp_meat_1_target,
            "cooking_on": cooking_state,
            "smoker_rate": smoker_rate,
            "timestamp": time.time()
        }
        # Initialize file modification timestamp
        last_params_file_timestamp = time.time()
    except Exception as e:
        logger.error(f"Error loading parameters: {e}")
        # Initialize last saved parameters with defaults
        last_saved_params = {
            "temp_air_target": temp_air_target,
            "temp_meat_1_target": temp_meat_1_target,
            "cooking_on": cooking_state,
            "smoker_rate": smoker_rate,
            "timestamp": time.time()
        }
        # Initialize file modification timestamp
        last_params_file_timestamp = time.time()


#######################################################################################################################
# Functions for InfluxDB
#######################################################################################################################

def check_influxdb_connection():
    """Check if InfluxDB connection is active and reconnect if needed"""
    global influxdb_connected, last_influxdb_reconnect_time, influx_write_client, influx_write_api

    # Only attempt reconnection if enough time has passed since last attempt
    if not influxdb_connected and time.time() - last_influxdb_reconnect_time >= INFLUXDB_RECONNECT_INTERVAL:
        try:
            # Try a ping or health check to see if connection is active
            health = influx_write_client.health()
            if health.status == "pass":
                influxdb_connected = True
                logger.info("InfluxDB connection is healthy")
            else:
                logger.error(f"InfluxDB health check failed: {health.message}")
                try_reconnect_influxdb()
        except Exception as e:
            logger.error(f"Error checking InfluxDB connection: {e}")
            try_reconnect_influxdb()


def try_reconnect_influxdb():
    """Try to reconnect to InfluxDB"""
    global influxdb_connected, last_influxdb_reconnect_time, influx_write_client, influx_write_api
    
    last_influxdb_reconnect_time = time.time()
    
    try:
        logger.info("Attempting to reconnect to InfluxDB...")
        # Close existing client if any
        if influx_write_client is not None:
            try:
                influx_write_client.close()
            except:
                pass
        
        # Create a new client
        influx_write_client = influxdb_client.InfluxDBClient(
            url=Smoker_Secrets.INFLUX_URL, 
            token=Smoker_Secrets.INFLUX_TOKEN, 
            org=Smoker_Secrets.INFLUX_ORG
        )
        
        # Create a new write API
        influx_write_api = influx_write_client.write_api(write_options=SYNCHRONOUS)
        
        # Test the connection with a health check
        health = influx_write_client.health()
        if health.status == "pass":
            influxdb_connected = True
            logger.info("Successfully reconnected to InfluxDB")
        else:
            influxdb_connected = False
            logger.error(f"Failed to reconnect to InfluxDB: {health.message}")
    except Exception as e:
        influxdb_connected = False
        logger.error(f"Failed to reconnect to InfluxDB: {e}")


def write_to_influx():
    global temp_air_top, temp_air_bottom, temp_meat_1, temp_air_target, temp_meat_1_target, cooking_state, fan_state_reported, heater_state_reported, influxdb_connected

    # Skip if not connected to InfluxDB
    if not influxdb_connected:
        logger.warning("Skipping write to InfluxDB as connection is not available")
        return

    # Create points for each measurement with explicit timezone and integer conversion
    points = [
        Point("smoker_telemetry")
            .tag("sensor", "temp_air_top")
            .field("temperature", int(temp_air_top))
            .time(datetime.now(timezone.utc)),
        Point("smoker_telemetry")
            .tag("sensor", "temp_air_bottom")
            .field("temperature", int(temp_air_bottom))
            .time(datetime.now(timezone.utc)),
        Point("smoker_telemetry")
            .tag("sensor", "temp_meat_1")
            .field("temperature", int(temp_meat_1))
            .time(datetime.now(timezone.utc)),
        Point("smoker_parameters")
            .tag("target", "temp_air")
            .field("temperature", int(temp_air_target))
            .time(datetime.now(timezone.utc)),
        Point("smoker_parameters")
            .tag("target", "temp_meat_1")
            .field("temperature", int(temp_meat_1_target))
            .time(datetime.now(timezone.utc)),
        Point("smoker_state")
            .tag("component", "cooking_state")
            .field("active", bool(cooking_state))
            .time(datetime.now(timezone.utc)),
        Point("smoker_state")
            .tag("component", "fan_state")
            .field("active", bool(fan_state_reported))
            .time(datetime.now(timezone.utc)),
        Point("smoker_state")
            .tag("component", "heater_state")
            .field("active", bool(heater_state_reported))
            .time(datetime.now(timezone.utc)),
        Point("smoker_state")
            .tag("component", "smoker_rate")
            .field("rate", int(smoker_rate))
            .time(datetime.now(timezone.utc)),
        Point("smoker_state")
            .tag("component", "smoker_state")
            .field("active", bool(smoker_state))
            .time(datetime.now(timezone.utc))
    ]

    try:
        # Write all points to InfluxDB
        influx_write_api.write(bucket=Smoker_Secrets.INFLUX_BUCKET, org=Smoker_Secrets.INFLUX_ORG, record=points)
        # If write succeeds, ensure connected status is true
        influxdb_connected = True
    except Exception as e:
        logger.error(f"Error writing to InfluxDB: {e}")
        # Mark as disconnected so we can try to reconnect
        influxdb_connected = False


#######################################################################################################################
# Functions for serial communication
#######################################################################################################################

# Define function to try to reconnect to serial port
def try_reconnect_serial():
    global pico_serial, serial_connected
    try:
        if 'pico_serial' in globals() and pico_serial:
            try:
                pico_serial.close()
            except:
                pass
        
        logger.info(f"Attempting to reconnect to Pi Pico on {SERIAL_PORT}...")
        pico_serial = serial.Serial(
            port=SERIAL_PORT,
            baudrate=SERIAL_BAUD,
            timeout=2.0
        )
        serial_connected = True
        logger.info(f"Successfully reconnected to Pi Pico on {SERIAL_PORT}")
    except Exception as e:
        logger.error(f"Failed to reconnect to Pi Pico: {e}")
        serial_connected = False


def send_command_to_pico(command):
    global serial_connected, pico_serial
    
    if not serial_connected:
        logger.error(f'send_command_to_pico: Serial not connected')
        return
        
    try:
        pico_serial.write(command.encode())
    except Exception as e:
        logger.error(f"Serial communication error: {e}")
        serial_connected = False  # Mark as disconnected so we can try to reconnect later


def read_pico_serial():
    global fan_state_reported, heater_state, serial_connected, heater_state_reported
    global temp_air_top, temp_air_bottom, temp_meat_1, smoker_rate, smoker_state
    
    if not serial_connected:
        logger.error(f'Serial not connected')
        return
    
    try:
        if pico_serial.in_waiting > 0:
            line = pico_serial.readline().decode('utf-8').rstrip()
            logger.debug(f'Pico serial: {line}')
            if line.startswith('{'):
                try:
                    data = json.loads(line)

                    if 'temp_air_top' in data:
                        temp_air_top = data['temp_air_top']
                    if 'temp_air_bottom' in data:
                        temp_air_bottom = data['temp_air_bottom']
                    if 'temp_meat' in data:
                        temp_meat_1 = data['temp_meat']
                    if 'heater_state' in data:
                        if data['heater_state'] == 'ON':
                            heater_state_reported = True
                        else:
                            heater_state_reported = False
                    if 'fan_state' in data:
                        if data['fan_state'] == 'ON':
                            fan_state_reported = True
                        else:
                            fan_state_reported = False
                    if 'smoker_state' in data:
                        if data['smoker_state'] == 'ON':
                            smoker_state = True
                        else:
                            smoker_state = False
                    if 'smoker_rate' in data:
                        smoker_rate = data['smoker_rate']
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e} in line: {line}")
    except Exception as e:
        logger.error(f"Error reading from serial: {e}")
        serial_connected = False


def deal_with_pico_comms():
    global serial_connected, last_pico_reconnect_time
    
    # Attempt to reconnect to serial if disconnected
    if not serial_connected and time.time() - last_pico_reconnect_time >= PICO_RECONNECT_INTERVAL:
        try_reconnect_serial()
        last_pico_reconnect_time = time.time()
        logger.debug(f'Reconnected to Pi Pico on {SERIAL_PORT}')
    
    read_pico_serial()


# Control smoker rate
def control_smoker():
    global smoker_rate, serial_connected
    
    if not serial_connected:
        return  # Skip control if not connected to serial

    send_command_to_pico(f'SMOKER_RATE {smoker_rate}\n')


# Control cooking state
def control_cooking_state():
    global cooking_state, serial_connected
    
    if not serial_connected:
        return  # Skip control if not connected to serial
    
    cooking_state_cmd = 1 if cooking_state else 0
    send_command_to_pico(f'COOKING_STATE {cooking_state_cmd}\n')
    logger.debug(f'Sent cooking state {cooking_state} to Pico')


#######################################################################################################################
# Variables
#######################################################################################################################
logger.info("Defining variables...")

# Temperatures
temp_air_top        = 100
temp_air_bottom     = 100
temp_air_target     = 225
temp_meat_1         = 100
temp_meat_1_target  = 190

# Communications
serial_connected             = False
wifi_connected               = False
last_pico_reconnect_time     = 0
influxdb_connected           = False
last_influxdb_reconnect_time = 0
last_params_file_timestamp   = 0  # Track last parameter file modification time

# States
cooking_state         = False
fan_state_reported    = False
heater_state          = False
heater_state_reported = False
smoker_state          = False
smoker_rate           = 30

#######################################################################################################################
# Initialization
#######################################################################################################################
logger.info("Initializing...")

# Load saved parameters
load_parameters()

try:
    # Initialize InfluxDB client
    influx_write_client = influxdb_client.InfluxDBClient(url=Smoker_Secrets.INFLUX_URL, token=Smoker_Secrets.INFLUX_TOKEN, org=Smoker_Secrets.INFLUX_ORG)
    influx_write_api = influx_write_client.write_api(write_options=SYNCHRONOUS)
    
    # Check the initial connection
    health = influx_write_client.health()
    if health.status == "pass":
        influxdb_connected = True
        logger.info("Connected to InfluxDB successfully")
    else:
        influxdb_connected = False
        logger.error(f"InfluxDB health check failed during initialization: {health.message}")
except Exception as e:
    influxdb_connected = False
    logger.error(f"Failed to initialize InfluxDB connection: {e}")


# Serial communication
try:
    pico_serial = serial.Serial(
        port=SERIAL_PORT,
        baudrate=SERIAL_BAUD,
        timeout=1.0  # 1 second timeout
    )
    serial_connected = True
    logger.info(f"Connected to Pi Pico on {SERIAL_PORT}")
except Exception as e:
    logger.error(f"Failed to connect to Pi Pico: {e}")
    serial_connected = False

#######################################################################################################################
# Main Loop
#######################################################################################################################
logger.info("Starting main loop...")


def main():
    try:
        # Timers
        last_update_time = time.time()
        last_save_time = time.time()
        last_influx_write_time = time.time()
        last_params_check_time = time.time()

        running = True
        while running:
            current_time = time.time()
            
            deal_with_pico_comms()
            check_influxdb_connection()

            # 1 second tasks
            if current_time - last_update_time >= 1:
                control_heater()
                control_smoker()
                control_cooking_state()
                last_update_time = current_time
                logger.debug(f'Temp air top: {temp_air_top}, Temp air bottom: {temp_air_bottom}, Temp meat 1: {temp_meat_1}, heater_state: {heater_state}, fan_state: {fan_state_reported}, smoker_rate: {smoker_rate}')

            # Check if parameters file has been modified by web app (every second)
            if current_time - last_params_check_time >= 1:
                if check_params_file_updated():
                    logger.info("Parameter file was modified externally, loading new parameters")
                    load_parameters()
                    # Update control components with new parameters immediately
                    control_heater()
                    control_smoker()
                    control_cooking_state()
                last_params_check_time = current_time

            # InfluxDB writes
            if current_time - last_influx_write_time >= INFLUX_WRITE_INTERVAL:
                write_to_influx()
                last_influx_write_time = current_time
                logger.debug(f'Wrote data to InfluxDB. Connection status: {influxdb_connected}')

            if time.time() - last_save_time >= SAVE_INTERVAL:
                save_parameters()
                last_save_time = current_time
                logger.debug(f'Saved parameters')

            time.sleep(0.03)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        logger.info("Exiting...")
        
        if serial_connected:
            try:
                pico_serial.close()
            except:
                pass
        sys.exit()


if __name__ == "__main__":
    main()
