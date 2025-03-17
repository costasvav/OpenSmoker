"""
WiFi credentials configuration file for OpenSmoker.
This file contains a list of WiFi networks to try connecting to.
"""

# List of WiFi networks to try connecting to
# Format: [SSID, Password]
WIFI_NETWORKS = [
    # Primary network
    ["SSID name", "password"],
    
    # Backup networks (add your own if needed)
    ["Backup_WiFi", "backup_password_here"],
    ["Workshop_WiFi", "workshop_password_here"],
]

# Advanced WiFi configuration
# These settings are optional and can be adjusted if needed
WIFI_CONFIG = {
    "country": "US",       # Country code (US, GB, etc.)
    "power_save": False,   # Disable power saving for better reliability
    "retry_limit": 3       # Number of connection retries before giving up
} 