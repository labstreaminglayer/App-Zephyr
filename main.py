"""Command line interface for the Zephyr BioHarness LSL integration."""

import logging
import datetime
import asyncio
import argparse

import pylsl

from core import BioHarness
from core.protocol import *

logger = logging.getLogger(__name__)


def add_manufacturer(desc):
    """Add manufacturer into to a stream's desc"""
    acq = desc.append_child('acquisition')
    acq.append_child_value('manufacturer', 'Medtronic')
    acq.append_child_value('model', 'Zephyr BioHarness')


# noinspection PyUnusedLocal
async def enable_ecg(link, nameprefix, idprefix, **kwargs):
    """Enable the ECG data stream. This is the raw ECG waveform."""
    info = pylsl.StreamInfo(nameprefix+'ECG', 'ECG', 1,
                            nominal_srate=ECGWaveformMessage.srate,
                            source_id=idprefix+'-ECG')
    desc = info.desc()
    chn = desc.append_child('channels').append_child('channel')
    chn.append_child_value('label', 'ECG1')
    chn.append_child_value('type', 'ECG')
    chn.append_child_value('unit', 'millivolts')
    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_ecg(msg):
        outlet.push_chunk([[v] for v in msg.waveform])

    await link.toggle_ecg(on_ecg)


# noinspection PyUnusedLocal
async def enable_respiration(link, nameprefix, idprefix, **kwargs):
    """Enable the respiration data stream. This is the raw respiration (chest
    expansion) waveform."""
    info = pylsl.StreamInfo(nameprefix+'Resp', 'Respiration', 1,
                            nominal_srate=BreathingWaveformMessage.srate,
                            source_id=idprefix+'-Resp')
    desc = info.desc()
    chn = desc.append_child('channels').append_child('channel')
    chn.append_child_value('label', 'Respiration')
    chn.append_child_value('type', 'EXG')
    chn.append_child_value('unit', 'unnormalized')
    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_breathing(msg):
        outlet.push_chunk([[v] for v in msg.waveform])

    await link.toggle_breathing(on_breathing)


# noinspection PyUnusedLocal
async def enable_accel100mg(link, nameprefix, idprefix, **kwargs):
    """Enable the accelerometer data stream. This is a 3-channel stream in units
    of 1 g (earth gravity)."""
    info = pylsl.StreamInfo(nameprefix+'Accel100mg', 'Mocap', 3,
                            nominal_srate=Accelerometer100MgWaveformMessage.srate,
                            source_id=idprefix+'-Accel100mg')
    desc = info.desc()
    chns = desc.append_child('channels')
    for lab in ['X', 'Y', 'Z']:
        chn = chns.append_child('channel')
        chn.append_child_value('label', lab)
        chn.append_child_value('unit', 'g')
        chn.append_child_value('type', 'Acceleration' + lab)
    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_accel100mg(msg):
        outlet.push_chunk([[x, y, z] for x, y, z in zip(msg.accel_x, msg.accel_y, msg.accel_z)])

    await link.toggle_accel100mg(on_accel100mg)


# noinspection PyUnusedLocal
async def enable_accel(link, nameprefix, idprefix, **kwargs):
    """Enable the regular accelerometer data stream. This is a 3-channel stream
    with slightly higher res than accel100mg (I believe around 2x), but """
    info = pylsl.StreamInfo(nameprefix+'Accel', 'Mocap', 3,
                            nominal_srate=AccelerometerWaveformMessage.srate,
                            source_id=idprefix+'-Accel')
    desc = info.desc()
    chns = desc.append_child('channels')
    for lab in ['X', 'Y', 'Z']:
        chn = chns.append_child('channel')
        chn.append_child_value('label', lab)
        chn.append_child_value('type', 'Acceleration' + lab)
        chn.append_child_value('unit', 'unnormalized')
    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_accel(msg):
        outlet.push_chunk([[x, y, z] for x, y, z in zip(msg.accel_x, msg.accel_y, msg.accel_z)])

    await link.toggle_accel(on_accel)


# noinspection PyUnusedLocal
async def enable_rtor(link, nameprefix, idprefix, **kwargs):
    """Enable the RR interval data stream. This has the interval between the
    most recent two ECG R-waves, in ms (held constant until the next R-peak),
    and the sign of the reading alternates with each new R peak."""
    info = pylsl.StreamInfo(nameprefix+'RtoR', 'Misc', 1,
                            nominal_srate=RtoRMessage.srate,
                            source_id=idprefix+'-RtoR')
    desc = info.desc()
    chn = desc.append_child('channels').append_child('channel')
    chn.append_child_value('label', 'RtoR')
    chn.append_child_value('unit', 'milliseconds')
    chn.append_child_value('type', 'Misc')

    add_manufacturer(desc)
    outlet = pylsl.StreamOutlet(info)

    def on_rtor(msg):
        outlet.push_chunk([[v] for v in msg.waveform])

    await link.toggle_rtor(on_rtor)


async def enable_events(link, nameprefix, idprefix, **kwargs):
    """Enable the events data stream. This has a few system events like button
    pressed, battery low, worn status changed."""
    info = pylsl.StreamInfo(nameprefix+'Markers', 'Markers', 1,
                            nominal_srate=0,
                            channel_format=pylsl.cf_string,
                            source_id=idprefix+'-Markers')
    outlet = pylsl.StreamOutlet(info)

    def on_event(msg):
        if kwargs.get('localtime', '1') == '1':
            stamp = datetime.datetime.fromtimestamp(msg.stamp)
        else:
            stamp = datetime.datetime.utcfromtimestamp(msg.stamp)
        timestr = stamp.strftime('%Y-%m-%d %H:%M:%S')
        event_str = f'{msg.event_string}/{msg.event_data}@{timestr}'
        outlet.push_sample([event_str])
        logger.debug(f'event detected: {event_str}')

    await link.toggle_events(on_event)


# noinspection PyUnusedLocal
async def enable_summary(link, nameprefix, idprefix, **kwargs):
    """Enable the summary data stream. This has most of the derived data
    channels in it."""
    # we're delaying creation of these objects until we got data since we don't
    # know in advance if we're getting summary packet V2 or V3
    info, outlet = None, None

    def on_summary(msg):
        nonlocal info, outlet
        content = msg.as_dict()
        if info is None:
            info = pylsl.StreamInfo(nameprefix+'Summary', 'Misc', len(content),
                                    nominal_srate=1,
                                    channel_format=pylsl.cf_float32,
                                    source_id=idprefix+'-Summary')
            desc = info.desc()
            add_manufacturer(desc)
            chns = desc.append_child('channels')
            for key in content:
                chn = chns.append_child('channel')
                chn.append_child_value('label', key)
                unit = get_unit(key)
                if unit is not None:
                    chn.append_child_value('unit', unit)
            outlet = pylsl.StreamOutlet(info)
        outlet.push_sample(list(content.values()))

    await link.toggle_summary(on_summary)


# noinspection PyUnusedLocal
async def enable_general(link, nameprefix, idprefix, **kwargs):
    """Enable the general data stream. This has summary metrics, but fewer than
    the summary stream, plus a handful of less-useful channels."""
    # we're delaying creation of these objects until we got data since we're
    # deriving the channel count and channel labels from the data packet
    info, outlet = None, None

    def on_general(msg):
        nonlocal info, outlet
        content = msg.as_dict()
        if info is None:
            info = pylsl.StreamInfo(nameprefix+'General', 'Misc', len(content),
                                    nominal_srate=1,
                                    channel_format=pylsl.cf_float32,
                                    source_id=idprefix+'-General')
            desc = info.desc()
            add_manufacturer(desc)
            chns = desc.append_child('channels')
            for key in content:
                chn = chns.append_child('channel')
                chn.append_child_value('label', key)
                unit = get_unit(key)
                if unit is not None:
                    chn.append_child_value('unit', unit)
            outlet = pylsl.StreamOutlet(info)
        outlet.push_sample(list(content.values()))

    await link.toggle_general(on_general)


# map of functions that enable various streams and hook in the respective handlers
enablers = {
    'ecg': enable_ecg,
    'respiration': enable_respiration,
    'accel100mg': enable_accel100mg,
    'accel': enable_accel,
    'rtor': enable_rtor,
    'events': enable_events,
    'summary': enable_summary,
    'general': enable_general,
}

# our BioHarness link
link = None


async def init():
    global link
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
        p.add_argument('--localtime', help="Whether event time stamps are in "
                                           "local time (otherwise UTC is assumed).",
                       default='1', choices=['0', '1'])
        args = p.parse_args()

        # set up logging
        logging.basicConfig(level=logging.getLevelName(args.loglevel),
                            format='%(asctime)s %(levelname)s: %(message)s')
        logger.info("starting up...")

        # sanity checking
        modalities = args.stream.split(',')
        unknown = set(modalities) - set(enablers.keys())
        if unknown:
            raise ValueError(f"Unknown modalities to stream: {unknown}")

        # connect to bioharness
        link = BioHarness(args.address, port=int(args.port), timeout=int(args.timeout))
        infos = await link.get_infos()
        info_str = '\n'.join([f' * {k}: {v}' for k, v in infos.items()])
        logger.info(f"Device info is:\n{info_str}")
        id_prefix = infos['serial']

        # enable various kinds of streams and install handlers
        logger.info("Enabling streams...")
        for mod in modalities:
            logger.info(f"  enabling {mod}...")
            enabler = enablers[mod]
            await enabler(link, nameprefix=args.streamprefix,
                          idprefix=id_prefix, **vars(args))

        logger.info('Now streaming...')

    except SystemExit:
        asyncio.get_event_loop().stop()
    except TimeoutError as e:
        logger.error(f"Operation timed out: {e}")
        asyncio.get_event_loop().stop()
    except Exception as e:
        logger.exception(e)
        asyncio.get_event_loop().stop()

if __name__ == "__main__":
    asyncio.ensure_future(init())
    loop = asyncio.get_event_loop()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Ctrl-C pressed.")
    finally:
        if link:
            # noinspection PyUnresolvedReferences
            link.shutdown()
        loop.close()
