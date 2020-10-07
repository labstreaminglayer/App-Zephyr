Zepyhr BioHarness LSL Integration
=================================

This is a simple LSL adapter for Medtronic / Zephyr BioModule and BioHarness 
Bluetooth devices. 

Prerequisites
============

- **Linux:** make sure that you have Bluetooth development headers installed
  e.g. on Ubuntu 20.04: `sudo apt install libbluetooth-dev`
- **Every Platform:** make sure that you have Miniconda installed and that the
  `conda` command-line interface is on your path 

Installation
============

- **Windows:** Invoke the script `run.cmd`, which will, if necessary, create a fresh Python 
  environment and install the necessary dependencies into it
- **Linux/MacOS:** Invoke the script `run.sh`, which will, if necessary, create a fresh Python 
  environment and install the necessary dependencies into it
- **Alternative manual install:** you can also follow the instructions in `conda-environment.yml` to install a 
  Python environment yourself, and then you can set up a script to run `main.py` 
  with a Python interpreter of your choosing


Usage
=====

1. Switch on the BioHarness using the button (it should blink orange and 
  optionally green as well).
2. Make sure that you can access the device from a vendor-provided desktop software
  (e.g., the one used to retrieve log files). 
3. Optionally configure it using the tools provided with the device
  (e.g., set subject info, time, and so on).
4. Run this application, optionally with command-line arguments, to stream
  real-time data over LSL. No other software is necessary to interface with the 
  device.
    - if you know the Bluetooth MAC address of the device (e.g., from a prior run),
      you can specify that via the command line as in `--address=12:34:56:78:9A` to 
      speed up the startup time
    - you can additionally override what modalities you want to stream using the 
      `--stream` argument (using fewer than all might extend the device's battery
      running time)
    - additional command-line arguments are available to further customize the
      program's behavior
    
License
=======

This software was developed by Syntrogi Inc. dba Intheon, and is licensed under 
the GPLv2. A copy of this license is provided in the file `COPYING`. 
