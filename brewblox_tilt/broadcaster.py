import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from . import mqtt, scanner, utils

LOGGER = logging.getLogger(__name__)

EXCEPTION_DELAY_S = 30


class Broadcaster:
    def __init__(self):
        config = utils.get_config()
        self.name = config.name

        self.scan_duration = max(config.scan_duration, 0.1)
        self.inactive_scan_interval = max(config.inactive_scan_interval, 0)
        self.active_scan_interval = max(config.active_scan_interval, 0)

        self.state_topic = f'brewcast/state/{self.name}'
        self.history_topic = f'brewcast/history/{self.name}'

        # Changes based on scan response
        self.scan_interval = 0
        self.prev_num_messages = 0

    async def run(self):
        mqtt_client = mqtt.CV.get()
        messages = await scanner.CV.get().scan(self.scan_duration)
        curr_num_messages = len(messages)
        prev_num_messages = self.prev_num_messages
        self.prev_num_messages = curr_num_messages

        # Adjust scan interval based on whether devices are detected or not
        if curr_num_messages == 0 or curr_num_messages < prev_num_messages:
            self.scan_interval = self.inactive_scan_interval
        else:
            self.scan_interval = self.active_scan_interval

        # Always broadcast a presence message
        # This will make the service show up in the UI even without active Tilts
        mqtt_client.publish(self.state_topic,
                            {
                                'key': self.name,
                                'type': 'Tilt.state.service',
                                'timestamp': utils.time_ms(),
                            },
                            retain=True)

        if not messages:
            return

        LOGGER.debug('\n - '.join([str(v) for v in ['Messages:', *messages]]))

        # Publish history
        # Devices can share an event
        mqtt_client.publish(self.history_topic,
                            {
                                'key': self.name,
                                'data': {
                                    msg.name: msg.data
                                    for msg in messages
                                },
                            })

        # Publish state
        # Publish individual devices separately
        # This lets us retain last published value if a device stops publishing
        timestamp = utils.time_ms()
        for msg in messages:
            mqtt_client.publish(f'{self.state_topic}/{msg.color}/{msg.mac}',
                                {
                                    'key': self.name,
                                    'type': 'Tilt.state',
                                    'timestamp': timestamp,
                                    'color': msg.color,
                                    'mac': msg.mac,
                                    'name': msg.name,
                                    'data': msg.data,
                                },
                                retain=True)

            for sync in msg.sync:
                if sync.type == 'TempSensorExternal':
                    mqtt_client.publish('brewcast/spark/blocks/patch',
                                        {
                                            'id': sync.block,
                                            'serviceId': sync.service,
                                            'type': 'TempSensorExternal',
                                            'data': {
                                                'setting[degC]': msg.data['temperature[degC]'],
                                            },
                                        })

    async def repeat(self):
        config = utils.get_config()
        while True:
            try:
                await asyncio.sleep(self.scan_interval)
                await self.run()
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=config.debug)
                await asyncio.sleep(EXCEPTION_DELAY_S)


@asynccontextmanager
async def lifespan():
    bc = Broadcaster()
    task = asyncio.create_task(bc.repeat())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
