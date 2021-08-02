import asyncio
import time
from random import random

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater

LOGGER = brewblox_logger(__name__)


def time_ms():
    return time.time_ns() // 1000000


def neutral_random():
    return random() - 0.5


class BroadcasterSim(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        config = app['config']
        self.name = config['name']
        self.active_scan_interval = max(config['active_scan_interval'], 0)
        self.colour = config['simulate']
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'

        self.interval = 1
        self.temp_c = 20
        self.temp_f = (self.temp_c * 9 / 5) + 32
        self.sg = 1.05
        self.signal = -80
        self.plato = 15

    async def prepare(self):
        pass

    async def run(self):
        await asyncio.sleep(self.interval)
        self.interval = self.active_scan_interval

        self.temp_c += (neutral_random() * 10)
        self.temp_f = (self.temp_c * 9 / 5) + 32
        self.sg += (neutral_random() / 100)
        self.signal += neutral_random()
        self.plato += (neutral_random() / 10)

        data = {
            'Temperature[degC]': self.temp_c,
            'Temperature[degF]': self.temp_f,
            'Specific gravity': self.sg,
            'Signal strength[dBm]': self.signal,
            'Plato[degP]': self.plato,
        }

        await mqtt.publish(self.app,
                           self.state_topic + f'/{self.colour}',
                           {
                               'key': self.name,
                               'type': 'Tilt.state',
                               'colour': self.colour,
                               'timestamp': time_ms(),
                               'data': data,
                           },
                           err=False,
                           retain=True)

        await mqtt.publish(self.app,
                           self.history_topic,
                           {
                               'key': self.name,
                               'data': {self.colour: data},
                           },
                           err=False)


def setup(app: web.Application):
    features.add(app, BroadcasterSim(app))
