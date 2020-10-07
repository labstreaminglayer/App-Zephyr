"""Command line interface or the Zephyr BioHarness LSL integration."""
import logging
import asyncio
import argparse

import pylsl

from bht import BioHarness
from bht.protocol import *

logger = logging.getLogger(__name__)


def add_manufacturer(desc):
    """Add manufacturer into to a stream's desc"""
    acq = desc.append_child('acquisition')
    acq.append_child_value('manufacturer', 'Medtronic')
    acq.append_child_value('model', 'Zephyr BioHarness')


async def enable_ecg(link, nameprefix, idprefix):
    """Enable the ECG data stream."""
    info = pylsl.StreamInfo(nameprefix+'ECG', 'ECG', 1,
                            nominal_srate=ECGWaveformMessage.srate,
                            source_id=idprefix+'-ECG')
    desc = info.desc()
    chn = desc.append_child('channels').append_child('channel')
    chn.append_child_value('label', 'ECG1')
    chn.append_child_value('type', 'ECG')  # TODO: unit
    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_ecg(msg):
        outlet.push_chunk([[v] for v in msg.waveform])

    await link.toggle_ecg(on_ecg)


async def enable_respiration(link, nameprefix, idprefix):
    """Enable the respiration data stream."""
    info = pylsl.StreamInfo(nameprefix+'Resp', 'Respiration', 1,
                            nominal_srate=BreathingWaveformMessage.srate,
                            source_id=idprefix+'-Resp')
    desc = info.desc()
    chn = desc.append_child('channels').append_child('channel')
    chn.append_child_value('label', 'Respiration')
    chn.append_child_value('type', 'EXG')  # TODO: unit
    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_breathing(msg):
        outlet.push_chunk([[v] for v in msg.waveform])

    await link.toggle_breathing(on_breathing)


async def enable_accel100mg(link, nameprefix, idprefix):
    """Enable the accelerometer data stream."""
    info = pylsl.StreamInfo(nameprefix+'Accel', 'Mocap', 3,
                            nominal_srate=AccelerometerWaveformMessage.srate,
                            source_id=idprefix+'-Accel')
    desc = info.desc()
    chns = desc.append_child('channels')
    for lab in ['X', 'Y', 'Z']:
        chn = chns.append_child('channel')
        chn.append_child_value('label', lab)
        chn.append_child_value('unit', 'g')
        chn.append_child_value('type', 'Acceleration' + lab)
    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_accel(msg):
        outlet.push_chunk([[x, y, z] for x, y, z in zip(msg.accel_x, msg.accel_y, msg.accel_z)])

    await link.toggle_accel100mg(on_accel)


async def enable_rtor(link, nameprefix, idprefix):
    """Enable the respiration data stream."""
    info = pylsl.StreamInfo(nameprefix+'RtoR', 'Misc', 1,
                            nominal_srate=RtoRMessage.srate,
                            source_id=idprefix+'-RtoR')
    desc = info.desc()
    chn = desc.append_child('channels').append_child('channel')
    chn.append_child_value('label', 'RtoR')
    chn.append_child_value('type', 'Misc')  # TODO: unit

    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_rtor(msg):
        outlet.push_chunk([[v] for v in msg.waveform])

    await link.toggle_rtor(on_rtor)


async def enable_events(link, nameprefix, idprefix):
    """Enable the respiration data stream."""
    info = pylsl.StreamInfo(nameprefix+'Markers', 'Markers', 1,
                            nominal_srate=0,
                            channel_format=pylsl.cf_string,
                            source_id=idprefix+'-Markers')
    outlet = pylsl.StreamOutlet(info)

    def on_event(msg):
        outlet.push_sample([str(msg.event_code) + ':' + msg.event_data.decode('utf-8')])

    await link.toggle_events(on_event)


# ma
enablers = {
    'ecg': enable_ecg,
    'respiration': enable_respiration,
    'accel100mg': enable_accel100mg,
    'rtor': enable_rtor,
    'events': enable_events,
}


async def init():
    try:
        # parse args
        p = argparse.ArgumentParser(
            description='Stream data from the Zephyr BioHarness.')
        p.add_argument('--address', help="Bluetooth MAC address of the device "
                                         "to use (autodiscover if not given).",
                       default='')
        p.add_argument('--port', help='Bluetooth port of the device (rarely '
                                      'used).',
                       default=1)
        p.add_argument('--stream', help='Comma-separated list of data to stream (no spaces).'
                                        'Note that using unnecessary streams will '
                                        'likely drain the battery faster.',
                       default=','.join(enablers.keys()))
        p.add_argument('--loglevel', help="Logging level (DEBUG, INFO, WARN, ERROR).",
                       default='INFO', choices=['DEBUG', 'INFO', 'WARN', 'ERROR'])
        p.add_argument('--streamprefix', help='Stream name prefix. This is pre-pended '
                                              'to the name of all LSL streams.',
                       default='Zephyr')
        p.add_argument('--timeout', help='Command timeout. If a command takes longer '
                                         'than this many seconds to succeed or fail, '
                                         'an error is raised and the app exits.',
                       default=20)
        args = p.parse_args()

        # set up logging
        logging.basicConfig(level=logging.getLevelName(args.loglevel),
                            format='%(asctime)s %(levelname)s: %(message)s')
        logger.info("starting up...")

        # enable various kinds of streams and install handlers
        modalities = args.stream.split(',')
        unknown = set(modalities) - set(enablers.keys())
        if unknown:
            raise ValueError(f"Unknown modalities to stream: {unknown}")

        # connect to bioharness
        link = BioHarness(args.address, port=int(args.port), timeout=args.timeout)
        infos = await link.get_infos()
        info_str = '\n'.join([f' * {k}: {v}' for k, v in infos.items()])
        logger.info(f"Device info is:\n{info_str}")
        id_prefix = infos['serial']

        logger.info("Enabling streams...")
        for mod in modalities:
            logger.info(f"  enabling {mod}...")
            enabler = enablers[mod]
            await enabler(link, nameprefix=args.streamprefix,
                          idprefix=id_prefix)

        logger.info('Now streaming...')

    except Exception as e:
        logger.exception(e)
        asyncio.get_event_loop().stop()

if __name__ == "__main__":
    asyncio.ensure_future(init())
    asyncio.get_event_loop().run_forever()
