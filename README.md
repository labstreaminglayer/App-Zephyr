Zephyr BioHarness LSL Integration
=================================

This LSL adapter facilitates the integration of Medtronic / Zephyr BioModule and BioHarness Bluetooth devices. If you encounter any issues with this program, please report them using the GitHub issue tracker for this project.

Prerequisites
=============

- **Linux:** Ensure that you have Bluetooth development headers installed
  (e.g., on Ubuntu 20.04: `sudo apt install libbluetooth-dev`).
- **Every Platform:** Ensure that you have Miniconda installed and that the `conda` command-line interface is in your system's path.

Since the Zephyr uses Bluetooth Low Energy (BLE), your machine needs to have the necessary wireless hardware installed (either built-in, as with many recent laptops, or by using a BLE-capable USB dongle).

Installing/Running
==================

- **Windows:** Execute the script `run.cmd`, which will, if necessary, create a fresh Python environment and install the required dependencies into it.
- **Linux/MacOS:** Execute the script `run.sh`, which will, if necessary, create a fresh Python environment and install the required dependencies into it.
- **Alternative manual install:** Alternatively, you can follow the instructions in `conda-environment.yml` to install a Python environment yourself or to add the necessary requirements to an existing environment. Then, use that interpreter to run `examples/sender.py`.

Usage
=====

1. Turn on the sensor using the button (it should either blink orange or have a constant orange LED).
2. Optionally, configure the device using the tools provided with the device (e.g., setting subject info, device clock, configuring logging, etc.).
3. Optionally, verify that you can access the device using vendor-provided desktop software (e.g., software used to retrieve log files), especially if this program seems unable to connect on its own.
4. Run the `sender.py` file from the examples folder, optionally with command-line arguments, to stream real-time data over LSL. No other software is necessary to interface with the device.
    - If you know the Bluetooth MAC address of the device (e.g., from a prior run), you can specify it via the command line as in `--address=12:34:56:78:9A` to expedite the startup time.
    - You can also override which modalities you want to stream using the `--stream` argument (streaming fewer modalities might extend the device's battery life). See Emitted Streams for a summary and the vendor documentation for complete details. By default, all data is streamed, equivalent to the argument `--stream=ecg,respiration,accel100mg,accel,rtor,events,summary,general`.
    - If you have multiple devices, it's advisable to use the `--streamprefix` argument to prefix the stream name with a string of your choice (e.g., `--streamprefix=Subject1`) to distinguish between multiple devices.
    - Additional command-line arguments are available to further customize the program's behavior. For more information on these, run the program with the `--help` argument.
5. Optionally, you can also run the `all_in_one.py` file from the examples folder. This will connect and stream the device data and also display it in real-time using matplotlib animation. Currently, only ECG and respiration data are enabled for real-time viewing, as they are the only 1D data streams live from the device.
6. Optionally, you can run `sender.py` in one instance and then run `receiver.py` in a different instance if you want more flexibility in running the project.

Important Concepts
==================

This app transmits Zephyr device data over a pylsl object. You can read about it at (https://github.com/chkothe/pylsl). In brief, we create a separate data stream for each data channel in the `sender.py` file and access it from the `receiver.py` file. You are encouraged to examine the animate function in the `receiver.py` file to understand how it works better.

Emitted Streams
===============

The application can generate the following streams (assuming the Zephyr stream name prefix). Refer to the vendor manual for complete details.

* **ZephyrECG:** The raw ECG waveform, in mV at 250 Hz (1 channel).
* **ZephyrResp:** The raw respiration (breathing) waveform, measuring chest expansion, at approximately 17.8 Hz, in unscaled units.
* **ZephyrAccel100mg:** A 3-channel stream with acceleration along the X, Y, and Z axes (coordinate system is configurable via vendor tools) at 50Hz, in units of g (earth acceleration).
* **ZephyrAccel:** Same as Accel100mg, but with higher numeric precision (>2x), in unscaled units.
* **ZephyrRtoR:** The interval between the most recent two ECG R-waves, in ms, at approximately 17.8 Hz. The value remains constant until the next R-wave is detected and alternates its sign with each new incoming R-wave.
* **ZephyrMarkers:** A marker stream with some device events (e.g., button pressed, battery low, worn status changed, and others), along with some event-specific numeric payload.
* **ZephyrSummary:** Summary metrics calculated at 1Hz. This stream includes over 60 channels, such as heart rate, respiration rate (beats/breaths per minute), HRV, various accelerometer-derived measures, confidence measures, and system status channels, among others.
* **ZephyrGeneral:** An alternative set of summary metrics (subset of summary, plus some channels of limited utility).

Acknowledgements
================

This open-source LSL application was developed and is maintained by Intheon (www.intheon.io).

For support inquiries, please file a GitHub issue on this repo (preferred) or contact support@intheon.io.

Copyright (C) 2020-2021 Syntrogi Inc. dba Intheon.

This work was funded by the Army Research Laboratory under Cooperative Agreement Number W911NF-10-2-0022.

Known Issues
============

Python's Bluetooth (LE) support on current macOS versions appears to be incomplete or broken, and this application is known not to run on macOS Big Sur, neither with conda's Python 3.7, the default Python 3.7, PyBlueZ 0.23, nor its current GitHub version (PyBlueZ 0.30). Older macOS versions might work but have not been tested.
