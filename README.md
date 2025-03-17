# OpenSmoker


### A completely open meat smoker controller

Welcome to a completely open BBQ meat smoker controller! With this you have control over the entire process, heating, fan, temperatures, and get alerts when different milestones are reached, and hack it into whatever you need!


## Inspiration

I am a builder and an avid meat lover.  I figured one day I shall start smoking meat (very soon after getting my own meat grinder for sausage making).  After seeing what's available on the market and at what prices, I decided it would be cheaper and funner to build my own smoker with a custom integrated controller that I can adapt and reprogram.  I wanted to automate as much as possible from the smoking process.  This is likely be an endless work-in-progress project, as I keep expanding its capabilities, but that is a good thing!


## Functionality
- 20x4 character LCD screen for displaying information and configuring settings
- 3 Temperature probes: 2 for air (top & bottom), 1 for meat
- Set target air and meat temperatures using buttons
- Automatic fan control for air circulation
- Reduce temperature when meat reaches target to prevent overcooking
- High heat detection and emergency shutdown (a.k.a. fire!)
- Panel mounted USB-C for easy reprogramming
- WiFi MQTT messaging for Home Assistant integration (WIP)
- Preset temperature profiles and configurations (WIP)


## Bill of Materials
Required:
1. Controller: Raspberry Pi Pico 2W
1. Temperature Sensors: 3x MAX6675 thermocouple amplifiers with k-type thermocouples
1. Display: 20x4 character LCD with I2C backpack
1. Heater Relay: Solid state relay SSR-25DA with heatsink 
1. Heating Element: 1200W 120VAC heater
1. Buttons: 3 standard momentary buttons
1. Switch: 12V rocker switch KCD2

Optional:
1. Fan Relay: 5-36V MOSFET relay
1. Adafruit Terminal PiCowbell breakout board
1. Panel Mount Cable USB-C female to Micro-B male cable

## Links
1. Raspberry Pi Pico 2W: https://www.adafruit.com/product/6087
1. Adafruit Terminal PiCowbell breakout board: https://www.adafruit.com/product/5907
1. USB-C to Micro-USB panel mount cable: https://www.adafruit.com/product/4056
1. Thermocouple amplifiers: https://www.amazon.com/dp/B0C6QTL5Y3
1. Heater element: https://www.amazon.com/dp/B0BLV846DB
1. Heater relay: https://www.amazon.com/dp/B09GLRRGLT
1. Switch: https://www.amazon.com/dp/B08YWQWF2J 
1. 20x4 LCD: https://www.amazon.com/Hosyond-Module-Display-Arduino-Raspberry/dp/B0C1G9GBRZ




