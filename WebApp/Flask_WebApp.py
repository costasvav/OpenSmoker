#!/bin/python3

from flask import Flask, render_template, request, Response, jsonify
import json
import sys
import os
import time
from datetime import datetime, timezone
# Add the parent directory to path to import smoker_secrets
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
import smoker_secrets

# InfluxDB client
from influxdb_client import InfluxDBClient
from influxdb_client.client.flux_table import FluxStructureEncoder
from influxdb_client import Point   
from influxdb_client.client.write_api import SYNCHRONOUS

app = Flask(__name__)

# InfluxDB configuration
INFLUX_URL = smoker_secrets.INFLUX_URL
INFLUX_TOKEN = smoker_secrets.INFLUX_TOKEN
INFLUX_ORG = smoker_secrets.INFLUX_ORG
INFLUX_BUCKET = smoker_secrets.INFLUX_BUCKET

# Parameters file path - same as defined in OpenSmoker.py
PARAMS_FILE = "/home/user/OpenSmoker_Parameters.json"

temp_air_target = 250
temp_meat_target = 205


# Initialize InfluxDB client
def get_influxdb_client():
    return InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG
    )

@app.route('/')
def index():
    return render_template('index.html')

# Get current smoker parameters
@app.route('/api/parameters', methods=['GET'])
def get_parameters():
    try:
        # Check if parameters file exists
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
                return jsonify(params)
        else:
            return jsonify({
                "error": "Parameters file not found",
                "message": "The smoker might not be running"
            }), 404
    except Exception as e:
        return jsonify({
            "error": "Failed to read parameters",
            "message": str(e)
        }), 500

# Control specific components
@app.route('/api/control/air-temperature', methods=['POST'])
def set_air_temperature():
    try:
        data = request.get_json()
        temperature = int(data.get('temperature'))
        
        # Validate temperature
        if temperature < 0 or temperature > 500:
            return jsonify({"error": "Invalid temperature range (0-500)"}), 400
            
        # Read current parameters
        params = {}
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        
        # Update air temperature target
        params['temp_air_target'] = temperature
        params['timestamp'] = time.time()
        
        # Write back to file
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f)
            
        return jsonify({"success": True, "temperature": temperature})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/control/meat-temperature', methods=['POST'])
def set_meat_temperature():
    try:
        data = request.get_json()
        temperature = int(data.get('temperature'))
        
        # Validate temperature
        if temperature < 0 or temperature > 300:
            return jsonify({"error": "Invalid temperature range (0-300)"}), 400
            
        # Read current parameters
        params = {}
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        
        # Update meat temperature target
        params['temp_meat_1_target'] = temperature
        params['timestamp'] = time.time()
        
        # Write back to file
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f)
            
        return jsonify({"success": True, "temperature": temperature})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/control/cooking-state', methods=['POST'])
def set_cooking_state():
    try:
        data = request.get_json()
        state = bool(data.get('state'))
        
        # Read current parameters
        params = {}
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        
        # Update cooking state
        params['cooking_on'] = state
        params['timestamp'] = time.time()
        
        # Write back to file
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f)
            
        return jsonify({"success": True, "state": state})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/control/smoker-rate', methods=['POST'])
def set_smoker_rate():
    try:
        data = request.get_json()
        rate = int(data.get('rate'))
        
        # Validate rate (assuming valid range is 0-100)
        if rate < 0 or rate > 100:
            return jsonify({"error": "Invalid smoker rate range (0-100)"}), 400
            
        # Read current parameters
        params = {}
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        
        # Update smoker rate
        params['smoker_rate'] = rate
        params['timestamp'] = time.time()
        
        # Write back to file
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f)
            
        return jsonify({"success": True, "rate": rate})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/data/air-temperatures')
def get_air_temperatures():
    # Get query parameters with default of 6h ago to now
    from_time = request.args.get('from', '-6h')
    
    # Convert relative time to absolute time
    if from_time.startswith('-'):
        # Calculate absolute time based on the relative duration
        duration = from_time[1:]
        # Use a simple string-based approach that InfluxDB understands
        from_time_flux = f"-{duration}"
    else:
        from_time_flux = from_time

    # Build Flux query with proper time format
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {from_time_flux})
      |> filter(fn: (r) => r._measurement == "smoker_telemetry")
      |> filter(fn: (r) => r.sensor == "temp_air_bottom" or r.sensor == "temp_air_top")
      |> filter(fn: (r) => r._field == "temperature")
    '''
    
    client = get_influxdb_client()
    query_api = client.query_api()
    
    try:
        result = query_api.query(query=query)
        
        # Process data for Plotly
        data = {
            "temp_air_top": [],
            "temp_air_bottom": []
        }
        
        for table in result:
            for record in table.records:
                sensor = record.values.get('sensor')
                timestamp = record.get_time().isoformat()
                value = record.get_value()
                
                if sensor == 'temp_air_top':
                    data["temp_air_top"].append({"time": timestamp, "value": value})
                elif sensor == 'temp_air_bottom':
                    data["temp_air_bottom"].append({"time": timestamp, "value": value})
        
        return jsonify(data)
    except Exception as e:
        # Log the error but return empty data to prevent UI from breaking
        print(f"Error querying air temperatures: {str(e)}")
        return jsonify({"temp_air_top": [], "temp_air_bottom": []})

@app.route('/api/data/meat-temperatures')
def get_meat_temperatures():
    # Get query parameters with default of 6h ago to now
    from_time = request.args.get('from', '-6h')
    
    # Convert relative time to absolute time
    if from_time.startswith('-'):
        # Calculate absolute time based on the relative duration
        duration = from_time[1:]
        # Use a simple string-based approach that InfluxDB understands
        from_time_flux = f"-{duration}"
    else:
        from_time_flux = from_time

    # Build Flux query with proper time format
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {from_time_flux})
      |> filter(fn: (r) => r._measurement == "smoker_telemetry")
      |> filter(fn: (r) => r.sensor == "temp_meat_1")
      |> filter(fn: (r) => r._field == "temperature")
    '''
    
    client = get_influxdb_client()
    query_api = client.query_api()
    
    try:
        result = query_api.query(query=query)
        
        # Process data for Plotly
        data = {
            "temp_meat_1": []
        }
        
        for table in result:
            for record in table.records:
                timestamp = record.get_time().isoformat()
                value = record.get_value()
                data["temp_meat_1"].append({"time": timestamp, "value": value})
        
        return jsonify(data)
    except Exception as e:
        # Log the error but return empty data to prevent UI from breaking
        print(f"Error querying meat temperatures: {str(e)}")
        return jsonify({"temp_meat_1": []})

@app.route('/api/data/target-temperatures')
def get_target_temperatures():
    # Get query parameters with default of 6h ago to now
    from_time = request.args.get('from', '-6h')
    
    # Convert relative time to absolute time
    if from_time.startswith('-'):
        # Calculate absolute time based on the relative duration
        duration = from_time[1:]
        # Use a simple string-based approach that InfluxDB understands
        from_time_flux = f"-{duration}"
    else:
        from_time_flux = from_time

    # Build Flux query with proper time format
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {from_time_flux})
      |> filter(fn: (r) => r._measurement == "smoker_parameters")
      |> filter(fn: (r) => r.target == "temp_air" or r.target == "temp_meat_1")
      |> filter(fn: (r) => r._field == "temperature")
    '''
    
    client = get_influxdb_client()
    query_api = client.query_api()
    
    try:
        result = query_api.query(query=query)
        
        # Process data for Plotly
        data = {
            "temp_air_target": [],
            "temp_meat_target": []
        }
        
        for table in result:
            for record in table.records:
                target = record.values.get('target')
                timestamp = record.get_time().isoformat()
                value = record.get_value()
                
                if target == 'temp_air':
                    data["temp_air_target"].append({"time": timestamp, "value": value})
                elif target == 'temp_meat_1':
                    data["temp_meat_target"].append({"time": timestamp, "value": value})
        
        return jsonify(data)
    except Exception as e:
        # Log the error but return empty data to prevent UI from breaking
        print(f"Error querying target temperatures: {str(e)}")
        return jsonify({"temp_air_target": [], "temp_meat_target": []})

@app.route('/api/data/component-state')
def get_component_state():
    # Get query parameters with default of 6h ago to now
    from_time = request.args.get('from', '-6h')
    
    # Convert relative time to absolute time
    if from_time.startswith('-'):
        # Calculate absolute time based on the relative duration
        duration = from_time[1:]
        # Use a simple string-based approach that InfluxDB understands
        from_time_flux = f"-{duration}"
    else:
        from_time_flux = from_time

    # Build Flux query with proper time format
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {from_time_flux})
      |> filter(fn: (r) => r._measurement == "smoker_state")
      |> filter(fn: (r) => r._field == "active" or r._field == "rate")
    '''
    
    client = get_influxdb_client()
    query_api = client.query_api()
    
    try:
        result = query_api.query(query=query)
        
        # Process data for Plotly
        data = {
            "cooking": [],
            "fan": [],
            "heater": [],
            "smoker_rate": []
        }
        
        for table in result:
            for record in table.records:
                component = record.values.get('component')
                timestamp = record.get_time().isoformat()
                
                if component == 'smoker_rate':
                    # For smoker_rate, use the actual value
                    value = record.get_value()
                    data["smoker_rate"].append({"time": timestamp, "value": value})
                elif component in data:
                    # For boolean components, convert to 1/0
                    value = 1 if record.get_value() else 0
                    data[component].append({"time": timestamp, "value": value})
        
        return jsonify(data)
    except Exception as e:
        # Log the error but return empty data to prevent UI from breaking
        print(f"Error querying component state: {str(e)}")
        return jsonify({"cooking": [], "fan": [], "heater": [], "smoker_rate": []})

# Get current smoker status
@app.route('/api/status', methods=['GET'])
def get_current_status():
    try:
        client = get_influxdb_client()
        query_api = client.query_api()
        
        # Build Flux query to get the most recent telemetry data
        query = f'''
        from(bucket: "{INFLUX_BUCKET}") 
          |> range(start: -1m)
          |> filter(fn: (r) => r._measurement == "smoker_telemetry" or r._measurement == "smoker_state")
          |> last()
        '''
        
        result = query_api.query(query=query)
        
        # Process the results into a status object
        status = {
            "temperatures": {
                "air_top": None,
                "air_bottom": None,
                "meat_1": None
            },
            "state": {
                "cooking": False,
                "fan": False,
                "heater": False,
                "smoker_rate": 0
            },
            "last_updated": None
        }
        
        for table in result:
            for record in table.records:
                # Update last_updated time with the most recent timestamp
                record_time = record.get_time().isoformat()
                if status["last_updated"] is None or record_time > status["last_updated"]:
                    status["last_updated"] = record_time
                
                # Parse temperature data
                if record.get_measurement() == "smoker_telemetry":
                    sensor = record.values.get('sensor')
                    if sensor == 'temp_air_top':
                        status["temperatures"]["air_top"] = record.get_value()
                    elif sensor == 'temp_air_bottom':
                        status["temperatures"]["air_bottom"] = record.get_value()
                    elif sensor == 'temp_meat_1':
                        status["temperatures"]["meat_1"] = record.get_value()
                
                # Parse state data
                if record.get_measurement() == "smoker_state":
                    component = record.values.get('component')
                    if component == 'cooking_state':
                        status["state"]["cooking"] = record.get_value()
                    elif component == 'fan_state':
                        status["state"]["fan"] = record.get_value()
                    elif component == 'heater_state':
                        status["state"]["heater"] = record.get_value()
                    elif component == 'smoker_rate':
                        status["state"]["smoker_rate"] = record.get_value()
        
        # Get the current target temperatures from parameters file
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
                status["target"] = {
                    "air": params.get('temp_air_target', temp_air_target),
                    "meat_1": params.get('temp_meat_1_target', temp_meat_target)
                }
        else:
            status["target"] = {
                "air": temp_air_target,
                "meat_1": temp_meat_target
            }
            
        return jsonify(status)
    except Exception as e:
        print(f"Error getting current status: {str(e)}")
        return jsonify({
            "error": "Failed to retrieve current status",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)

