import asyncio
import time
from typing import Any, List

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater, strex

from brewblox_tilt import blescan, parser

LOGGER = brewblox_logger(__name__)

EXIT_DELAY_S = 30


def time_ms():
    return time.time_ns() // 1000000


async def _open_socket() -> Any:
    try:
        return blescan.open_socket()

    except Exception as e:
        LOGGER.error(f'Error accessing bluetooth device: {strex(e)}', exc_info=True)
        await asyncio.sleep(EXIT_DELAY_S)  # Avoid lockup caused by service reboots
        raise web.GracefulExit(1)


async def _scan_socket(sock) -> List[blescan.TiltEventData]:
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, blescan.scan, sock, 10)

    except Exception as e:
        LOGGER.error(f'Error accessing bluetooth device whilst scanning: {strex(e)}', exc_info=True)
        await asyncio.sleep(EXIT_DELAY_S)  # Avoid lockup caused by service reboots
        raise web.GracefulExit(1)


class Broadcaster(repeater.RepeaterFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)

        config = app['config']
        self.name = config['name']
        self.inactive_scan_interval = max(config['inactive_scan_interval'], 0)
        self.active_scan_interval = max(config['active_scan_interval'], 0)
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'

        self.sock = None
        self.parser = parser.EventDataParser(app)
        self.interval = 1
        self.prev_num_events = 0

    async def prepare(self):
        self.sock = await _open_socket()

    async def run(self):
        await asyncio.sleep(self.interval)
        events = await _scan_socket(self.sock)
        message = self.parser.parse(events)

        curr_num_events = len(message)
        prev_num_events = self.prev_num_events
        self.prev_num_events = curr_num_events

        # Adjust scan interval based on whether devices are detected or not
        if curr_num_events == 0 or curr_num_events < prev_num_events:
            self.interval = self.inactive_scan_interval
        else:
            self.interval = self.active_scan_interval

        if not message:
            return

        LOGGER.debug(message)

        # Publish history
        # Colours can share an event
        await mqtt.publish(self.app,
                           self.history_topic,
                           {
                               'key': self.name,
                               'data': message,
                           },
                           err=False)

        # Publish state
        # Publish individual colours separately
        # This lets us retain last published values for all colours
        timestamp = time_ms()
        for (colour, submessage) in message.items():
            await mqtt.publish(self.app,
                               f'{self.state_topic}/{colour}',
                               {
                                   'key': self.name,
                                   'type': 'Tilt.state',
                                   'colour': colour,
                                   'timestamp': timestamp,
                                   'data': submessage,
                               },
                               err=False,
                               retain=True)


def setup(app):
    features.add(app, Broadcaster(app))
