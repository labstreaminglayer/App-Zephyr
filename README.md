Zepyhr BioHarness LSL Integration
=================================

This is an LSL adapter for Medtronic / Zephyr BioModule and BioHarness 
Bluetooth devices. This is a new application, so if you find any issues with it,
please use the GitHub issue tracker for this project to report them. 

Prerequisites
============

- **Linux:** make sure that you have Bluetooth development headers installed
  (e.g. on Ubuntu 20.04: `sudo apt install libbluetooth-dev`)
- **Every Platform:** make sure that you have Miniconda installed and that the
  `conda` command-line interface is on your path

Since the Zephyr uses Bluetooth Low Energy (BLE), your machine needs to have the
necessary wireless hardware installed (either built in as with many recent laptops,
or using a BLE-capable USB dongle).

Installation
============

- **Windows:** Invoke the script `run.cmd`, which will, if necessary, create a fresh Python 
  environment and install the necessary dependencies into it
- **Linux/MacOS:** Invoke the script `run.sh`, which will, if necessary, create a fresh Python 
  environment and install the necessary dependencies into it
- **Alternative manual install:** you can also follow the instructions in 
  `conda-environment.yml` to install a Python environment yourself or to add the
  necessary requirements to an existing environment, and then you can use that
  interpreter to run `main.py`


Usage
=====

1. Switch on the sensor using the button (it should either blink orange or 
   have a constant orange LED).
2. Optionally configure the device using the tools provided with the device
  (e.g., set subject info, device clock, configure logging, and so on).
3. Optionally check that you can access the device from a vendor-provided 
  desktop software (e.g., the one used to retrieve log files), particularly if
  this program appears unable to connect by itself. 
4. Run this application, optionally with command-line arguments, to stream
  real-time data over LSL. No other software is necessary to interface with the 
  device.
    - if you know the Bluetooth MAC address of the device (e.g., from a prior run),
      you can specify that via the command line as in `--address=12:34:56:78:9A` to 
      speed up the startup time
    - you can additionally override what modalities you want to stream using the 
      `--stream` argument (using fewer than all might extend the device's battery
      running time). By default, the device streams out quite a number of modalities,
      including ECG, respiration, R-to-R intervals, two accelerometer streams
      with different resolutions/ranges (one with a 0.1g resolution called 
      accel100mg, and another called accel with a somewhat higher resolution that 
      does, however, output unscaled sensor readings), event codes (button 
      presses, jumps etc), and a highly-useful 1Hz summary stream with numerous 
      derived metrics, and a second 1Hz "general" stream that has some additional
      metrics (but otherwise overlaps with summary). By default, everything
      is streamed, which is equivalent to the argument 
      `--stream=ecg,respiration,accel100mg,accel,rtor,events,summary,general`.      
    - if you have multiple devices, it can be a good idea to use the 
      `--streamprefix` argument to prefix the stream name with a string of 
      your choice (e.g., `--streamprefix=Subject1`) to disambiguate multiple 
      devices.
    - additional command-line arguments are available to further customize the
      program's behavior, for further information on these, run the program 
      with the `--help` argument
    
License
=======

This software was developed by Syntrogi Inc. dba Intheon, and is licensed under 
the GPLv2. A copy of this license is provided in the file `COPYING`. 
