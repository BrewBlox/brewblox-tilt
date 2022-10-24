import asyncio
import time
from random import uniform

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater

from brewblox_tilt import const, parser

LOGGER = brewblox_logger(__name__)


def time_ms():
    return time.time_ns() // 1000000


class Simulation:

    def __init__(self, simulated: str) -> None:
        self.uuid = next((
            uuid
            for uuid, color in const.TILT_UUID_COLORS.items()
            if color.upper() == simulated.upper()
        ), '')
        self.mac = self.uuid.replace('-', '').upper()[:12]

        self.interval = 1
        self.temp_f = 68
        self.raw_sg = 1050
        self.rssi = -80

    def update(self) -> parser.TiltEvent:
        self.temp_f += uniform(-2, 2)
        self.raw_sg += uniform(-10, 10)
        self.rssi += uniform(-1, 1)

        return parser.TiltEvent(mac=self.mac,
                                uuid=self.uuid,
                                major=self.temp_f,
                                minor=self.raw_sg,
                                txpower=0,
                                rssi=self.rssi)


class BroadcasterSim(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        config = app['config']
        self.name = config['name']
        self.active_scan_interval = max(config['active_scan_interval'], 0)
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'
        self.names_topic = f'brewcast/tilt/{self.name}/names'

        self.interval = 1
        self.parser = parser.EventDataParser(app)
        self.simulations = [Simulation(simulated)
                            for simulated in config['simulate']]

        LOGGER.info(f'Started simulation for {config["simulate"]}')

    async def on_names_change(self, topic: str, data: dict):
        self.parser.apply_custom_names(data)

    async def prepare(self):
        await mqtt.listen(self.app, self.names_topic, self.on_names_change)
        await mqtt.subscribe(self.app, self.names_topic)

    async def shutdown(self, app: web.Application):
        await mqtt.unsubscribe(app, self.names_topic)
        await mqtt.unlisten(app, self.names_topic, self.on_names_change)

    async def run(self):
        await asyncio.sleep(self.interval)
        self.interval = self.active_scan_interval

        events = {sim.mac: sim.update() for sim in self.simulations}
        messages = self.parser.parse(list(events.values()))

        await mqtt.publish(self.app,
                           self.state_topic,
                           {
                               'key': self.name,
                               'type': 'Tilt.state.service',
                               'timestamp': time_ms(),
                           },
                           err=False,
                           retain=True)

        if not messages:
            return

        LOGGER.debug(messages)

        # Publish history
        # Devices can share an event
        await mqtt.publish(self.app,
                           self.history_topic,
                           {
                               'key': self.name,
                               'data': {
                                   msg.name: msg.data
                                   for msg in messages
                               },
                           },
                           err=False)

        # Publish state
        # Publish individual devices separately
        # This lets us retain last published value if a device stops publishing
        timestamp = time_ms()
        for msg in messages:
            await mqtt.publish(self.app,
                               f'{self.state_topic}/{msg.color}/{msg.mac}',
                               {
                                   'key': self.name,
                                   'type': 'Tilt.state',
                                   'timestamp': timestamp,
                                   'color': msg.color,
                                   'mac': msg.mac,
                                   'name': msg.name,
                                   'data': msg.data,
                               },
                               err=False,
                               retain=True)

            for sync in msg.sync:
                if sync.type == 'Spark.Temperature':
                    await mqtt.publish(self.app,
                                       'brewcast/spark/blocks/patch',
                                       {
                                           'id': sync.block,
                                           'serviceId': sync.service,
                                           'type': 'TempSensorExternal',
                                           'data': {
                                               'setting[degC]': msg.data['temperature[degC]'],
                                           },
                                       },
                                       err=False)


def setup(app: web.Application):
    features.add(app, BroadcasterSim(app))
