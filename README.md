# OpenSmoker


### A completely open and hackable BBQ meat smoker controller

Welcome to a completely open BBQ meat smoker controller! With this you have control over the entire smoking process: heating, fan, temperatures, profiles, and even alerts when different milestones are reached!  And better yet, it is hackable into whatever you need to accomplish!

It is definitely very much a work in progress and will be improved upon with every smoke I complete!

<img src="images/Pi_Splash.png" alt="OpenSmoker Controller" style="max-width: 400px;">

(AI generated logo)

### Latest Updates (May 18th):

New Gridfinity modular layout:

<img src="images/PXL_20250518_152825725.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Portable case:

<img src="images/PXL_20250518_153003515.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Live Flask dashboards:

<img src="images/PXL_20250518_153008204.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

<img src="images/Screenshot 2025-05-10 114720.png" alt="OpenSmoker Controller" style="max-width: 400px;">


Not pretty but works:

<img src="images/PXL_20250427_221355949.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">


## Inspiration

I am a builder, tinkerer, programmer, and love a good smoked meat (I'm from Texas afterall).  I figured one day I shall start smoking meat (very soon after getting my own meat grinder for sausage making).  After seeing what's available on the market and at what prices and the complexity of manning a pit for hours on end, I decided it would be cheaper and funner to build my own smoker with a custom integrated controller that can control as much of the process as possible.  I want to automate everything!  This is likely be an endless work-in-progress project, as I keep expanding its capabilities, but that is a good thing, right?!


## Functionality

- Touchscreen LCD display with realtime dashboards of current conditions, targets, controls etc.
- WiFi enabled.
- Dashboards accessible from any computer on the network.
- 3 Temperature probes: 2 for air, 1 for meat.
- Set target air and meat temperatures from the display.
- Automatic fan control for air circulation.
- Reduce temperature when meat reaches target to prevent overcooking.
- High heat detection and emergency shutdown (a.k.a. fire!).
- Customizable cooking profiles and configurations (WIP).


## Design

A lot of the design is dictated by what hardware I had laying around and also from a few different design iterations of what worked well and what didn't.

I also opted for a laser-cut gridfinity-compatible design to be as modular as possible.

I am using a Raspberry Pi 4B as the main brains of the operation.  It stores all the data, performs the bulk of the logic, communicates with the microcontroller, hosts the dashboards for local or remote viewing, and allows for a lot of added functionality down the line.  

The microcontroller, a Pi Pico 2W here, controls the actual parts, the heaters, sensors, fan, etc.  This is for reliability should the Pi 4B fail or restart.  The code has failsafes in place to help prevent dangerous situations.

I am using a small 13" pelican case to house everything. This way, when I am not using the smoker, I can disconnect the cables and bring it inside.  I am using XT30 and XT60 plugs to connect to power and components.


## Bill of Materials

Modules (gridfinity size):
1. Display: WaveShare 10.1" DSI LCD with touch
1. SBC (3x2): Most modern SBCs should work, e.g. Raspberry Pi 3+, Jetson etc.
1. Microcontroller (2x2): Raspberry Pi Pico 1/2
1. Temperature Sensors (1x1): 2x Adafruilt MCP9600 I2C, 1x MAX31865 SPI
1. Heater Relay (2x2): Solid state relay SSR-25DA with heatsink and active 24V cooling fan.
1. SBC Power Supply (2x1): Any power supply capable of powering the computer
1. Fan Power Supply (2x1): Any power supply capable of powering the fan
1. Main Heating Element: 1200W 120VAC heater
1. Smoke Heating Element: 200W 120VAC heater from a Traeger pellet smoker
1. Fuse: 15A fuse


Tooling:
1. Laser Cutter (I used a 5W Creality cutter to cut 5mm plywood), a 3D printer could also be used.
1. Soldering Iron.


## Setup

1. Flash clean RPiOS to SD card
1. Install & setup InfluxDB
1. Copy over scripts to Pi
1. Setup both scripts to run at startup (e.g. with systemd)
1. Flash Arduino code to microcontroller


## My progress in pictures

### First version:

Here is my first iteration trying to do everything with only a Pi Pico 2W.
Too many difficulties with pure-microcontroller system.  But it was nice and clean.

Front face:

<img src="images/PXL_20250316_184249141.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Spagetti wires:

<img src="images/PXL_20250316_184118530.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Front panel backside:

<img src="images/PXL_20250316_184126729.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Better inside view:

<img src="images/PXL_20250316_184135381.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

In action:

<img src="images/PXL_20250316_185002139.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Separate meat thermometer for initial testing:

<img src="images/PXL_20250317_000621267.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

We have smoke! Latch broke, so using a plywood box to keep door shut. 

<img src="images/PXL_20250317_000536843.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Getting color after about 90 minutes!  Put wood chips directly on heating element.

<img src="images/PXL_20250317_000636924.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

### V2 Redesign:

<img src="images/PXL_20250408_222655028.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Testing Grafana dashboards:

<img src="images/Screenshot 2025-04-08 151454.png" alt="OpenSmoker Controller" style="max-width: 400px;">
<img src="images/Screenshot 2025-04-09 075047.png" alt="OpenSmoker Controller" style="max-width: 400px;">

Testing on some brisket flat and point separate:

<img src="images/PXL_20250414_213009630.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

### V2.1 Modular Upgrades:

Gridfinity and 10" LCD:

<img src="images/PXL_20250427_190540695.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Sausage time:

<img src="images/PXL_20250427_191828116.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Better insulation on enclosure:

<img src="images/PXL_20250427_221355949.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Andouille results (perfect!):

<img src="images/PXL_20250427_224147703.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

First pulled pork:

<img src="images/PXL_20250510_144735233.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Progress:

<img src="images/PXL_20250510_172321851.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Final product:

<img src="images/PXL_20250510_182933836.MP.jpg" alt="OpenSmoker Controller" style="max-width: 400px;">

Flask Dashboard, you can tell when I open the door for more checking on it:

<img src="images/Screenshot 2025-05-10 114720.png" alt="OpenSmoker Controller" style="max-width: 400px;">
