# OpenSmoker


### A completely open meat smoker controller

Welcome to a completely open BBQ meat smoker controller! Have control over how much heat you need, what internal temperature you are targeting, get alerts when different milestones are reached, and hack it into whatever you need!


## Inspiration

I am a builder and an avid meat lover.  I figured one day I shall start smoking meat.  After seeing what's available on the market and at what price, I decided it would be cheaper and funner to build my own smoker with a custom integrated controller.  I wanted to automate as much as possible from the smoking process.  This is likely be an endless work-in-progress, as I keep expanding its capabilities.


## Functionality
- LCD screen for displaying information and configuring settings
- Set smoking air temperature
- Monitor meat temperature
- Monitor smoker air temperature at 2 locations, top and bottom of enclosure
- Automatic fan control for air circulation when the difference between top and bottom temps are too high
- Reduce air temperature when meat reaches target to prevent overcooking
- High heat detection and emergency shutdown (fire!)
- WiFi MQTT messaging for Home Assistant integration (WIP)
- Preset temperature profiles and configurations (WIP)


## Bill of Materials
1. Controller: Raspberry Pi Pico W
1. Temperature Sensors: 3x MAX6675 thermocouple amplifiers with k-type thermocouples
1. Display: 20x4 character LCD with I2C
1. Fan Relay: MOSFET relay
1. Heater Relay: Solid state relay with heatsink SSR-25DA
1. Heating Element: 1200W 120V heater
1. Air vents: 2x Stainless steel rotating vents
1. Dial Controller: Rotary encoder with push button KY-040
1. Switch: 12V rocker switch KCD2


## Links
1. Thermocouple Amplifiers: https://www.amazon.com/dp/B0C6QTL5Y3
1. Heating Element: https://www.amazon.com/dp/B0BLV846DB
1. Vents: https://www.amazon.com/dp/B0C6R22VBZ
1. Heater Relay: https://www.amazon.com/dp/B09GLRRGLT
1. Baking Grate: https://www.amazon.com/dp/B085P1764K
1. Rotary Encoder: https://www.amazon.com/JTAREA-KY-040-Encoder-Encoders-Modules/dp/B0D2TTG858
1. Switch: https://www.amazon.com/dp/B08YWQWF2J 
1. LCD: https://www.amazon.com/Hosyond-Module-Display-Arduino-Raspberry/dp/B0C1G9GBRZ




