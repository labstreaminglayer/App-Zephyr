Zepyhr BioHarness LSL Integration
=================================


Installation
============



Linux
-----
- make sure that you have Bluetooth development headers installed
  e.g. on Ubuntu 20.04: `sudo apt install libbluetooth-dev`


All platforms
-------------
- make sure that you have Miniconda installed and/or that the
  `conda` command-line interface is on your path
- follow the instructions in `conda-environment.yml` to see how to install
  an environment


Usage
=====

- switch on the BioHarness
- optionally configure it using the tools provided with the device
  (e.g., set subject info, time, and so on)
- run this program, optionally with command-line arguments, to stream
  real-time data over LSL
  - if you know the Bluetooth MAC address of the device (e.g., from a prior run),
    you can specify that via the command line as in '--address=12:34:56:78:9A' to 
    speed up the startup time
  - you can additionally override what modalities you want to stream using the 
    `--stream` argument (using fewer than all might extend the device's battery
    running time)
  - additional command-line arguments are available to further customize the
    program's behavior
    
  