"""Command line interface for the Zephyr BioHarness LSL integration."""
import numpy as np
from matplotlib import pyplot as plt
from pylsl import StreamInlet
from matplotlib.animation import FuncAnimation
import matplotlib.ticker as ticker

import logging
import argparse

import pylsl
logger = logging.getLogger(__name__)


def animate(i, signals: {str: StreamInlet}, axs: dict, first_time_stamp: list[float]):
    lines = []
    for stream_name, stream in signals.items():
        samples, timestamps = stream.pull_chunk()
        if len(samples) > 0:
            xs = []
            for sample in samples:
                if isinstance(sample, list):
                    xs.append(sample[0])
                else:
                    xs.append(float(sample))
            if first_time_stamp[0] == 0:
                first_time_stamp[0] = timestamps[0]
            timestamps = np.array(timestamps) - first_time_stamp[0]
            lines.append(axs[stream_name].plot(timestamps, xs)[0])
    return list(axs.values())


def receive():
    all_signals_names = ['ECG', 'Respiration']
    p = argparse.ArgumentParser(
        description='Receive data from the Zephyr BioHarness.')
    p.add_argument('--stream', help='Comma-separated list of data to stream (no spaces).'
                                    'Note that using unnecessary streams will '
                                    'likely drain the battery faster.',
                   default=','.join(all_signals_names))
    args = p.parse_args()
    modalities = args.stream.split(',')
    signals = {}
    unknown = set(modalities) - set(all_signals_names)
    if unknown:
        raise ValueError(f"Unknown modalities to stream: {unknown}")
    for mod in modalities:
        streams = pylsl.resolve_stream('type', mod)
        if len(streams) > 0:
            signals[mod] = pylsl.StreamInlet(streams[0])
    fig, axs = plt.subplots(len(signals.keys()), 1, figsize=(10, 6))
    plt.subplots_adjust(hspace=1 / len(signals.keys()))
    axes = {}
    sample_rate = 250
    interval_size = 1000 // sample_rate
    first_time_stamp = [0]
    for i, stream_name in enumerate(signals.keys()):
        axes[stream_name] = axs[i]
        ax = axes[stream_name]
        ax.set_title(f"{stream_name}")
        ax.ticklabel_format(useOffset=False, style='plain', axis='x')
        ax.xaxis.set_major_formatter(ticker.ScalarFormatter())

    # Create a StreamInlet to read from the stream.
    ani = FuncAnimation(fig, animate, fargs=(signals, axes, first_time_stamp), interval=interval_size)
    plt.show()


if __name__ == "__main__":
    receive()
