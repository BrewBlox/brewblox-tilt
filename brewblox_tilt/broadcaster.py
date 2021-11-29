import asyncio
import time
from pathlib import Path

from aiohttp import web
from beacontools import (BeaconScanner, BluetoothAddressType,
                         IBeaconAdvertisement, IBeaconFilter)
from beacontools.scanner import HCIVersion
from brewblox_service import brewblox_logger, features, mqtt, repeater

from brewblox_tilt import const, parser

LOGGER = brewblox_logger(__name__)

HCI_SCAN_INTERVAL_S = 30


def time_ms():
    return time.time_ns() // 1000000


class Broadcaster(repeater.RepeaterFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)

        config = app['config']
        self.name = config['name']
        self.inactive_scan_interval = max(config['inactive_scan_interval'], 0)
        self.active_scan_interval = max(config['active_scan_interval'], 0)
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'
        self.names_topic = f'brewcast/tilt/{self.name}/names'

        self.scanner = None
        self.parser = parser.EventDataParser(app)
        self.interval = 1
        self.prev_num_messages = 0
        self.events: dict[str, parser.TiltEvent] = {}

    @property
    def scanner_active(self) -> bool:
        return self.scanner and self.scanner._mon.is_alive()

    async def on_event(self, mac: str, rssi: int, packet: IBeaconAdvertisement, info: dict):
        LOGGER.debug(f'Recv {mac=} {packet.uuid=}, {packet.major=}, {packet.minor=}')
        self.events[mac] = parser.TiltEvent(mac=mac,
                                            uuid=packet.uuid,
                                            major=packet.major,
                                            minor=packet.minor,
                                            txpower=packet.tx_power,
                                            rssi=rssi)

    async def on_names_change(self, topic: str, data: dict):
        self.parser.apply_custom_names(data)

    async def detect_device_id(self) -> int:
        bt_dir = Path('/sys/class/bluetooth')
        device_id: int = None
        LOGGER.info('Looking for Bluetooth adapter...')
        while device_id is None:
            hci_devices = sorted(f.name for f in bt_dir.glob('./hci*'))
            if hci_devices:
                device_id = int(hci_devices[0].removeprefix('hci'))
                LOGGER.info(f'Found Bluetooth adapter hci{device_id}')
            else:
                LOGGER.debug(f'No Bluetooth adapter available. Retrying in {HCI_SCAN_INTERVAL_S}s...')
                await asyncio.sleep(HCI_SCAN_INTERVAL_S)
        return device_id

    def apply_pi4_hack(self):
        model_file = Path('/sys/firmware/devicetree/base/model')
        if not model_file.exists():
            return
        content = model_file.read_text()
        if 'Pi 4' in content:
            # https://github.com/citruz/beacontools/issues/65
            LOGGER.info('Pi 4 detected. Applying Bluetooth version hack.')
            self.scanner._mon.get_hci_version = lambda: HCIVersion.BT_CORE_SPEC_4_2

    async def prepare(self):
        await mqtt.listen(self.app, self.names_topic, self.on_names_change)
        await mqtt.subscribe(self.app, self.names_topic)

        device_id = await self.detect_device_id()
        loop = asyncio.get_running_loop()
        self.scanner = BeaconScanner(
            lambda *args: asyncio.run_coroutine_threadsafe(self.on_event(*args), loop),
            bt_device_id=device_id,
            device_filter=[
                IBeaconFilter(uuid=uuid)
                for uuid in const.TILT_UUID_COLORS.keys()
            ],
            scan_parameters={
                'address_type': BluetoothAddressType.PUBLIC,
            })
        self.apply_pi4_hack()
        self.scanner.start()

    async def shutdown(self, app: web.Application):
        await mqtt.unsubscribe(app, self.names_topic)
        await mqtt.unlisten(app, self.names_topic, self.on_names_change)
        if self.scanner:
            self.scanner.stop()
            self.scanner = None

    async def run(self):
        await asyncio.sleep(self.interval)

        if not self.scanner_active:
            LOGGER.error('Bluetooth scanner exited prematurely')
            raise web.GracefulExit(1)

        messages = self.parser.parse(list(self.events.values()))
        self.events.clear()

        curr_num_messages = len(messages)
        prev_num_messages = self.prev_num_messages
        self.prev_num_messages = curr_num_messages

        # Adjust scan interval based on whether devices are detected or not
        if curr_num_messages == 0 or curr_num_messages < prev_num_messages:
            self.interval = self.inactive_scan_interval
        else:
            self.interval = self.active_scan_interval

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


def setup(app):
    features.add(app, Broadcaster(app))
