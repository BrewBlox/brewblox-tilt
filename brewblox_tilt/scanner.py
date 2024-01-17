import asyncio
import logging
from abc import ABC, abstractmethod
from contextvars import ContextVar
from random import uniform
from uuid import UUID

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from construct import Array, Byte, Const, Int8sl, Int16ub, Struct
from construct.core import ConstError

from . import const, parser, utils
from .models import TiltEvent, TiltMessage

BEACON_STRUCT = Struct(
    'type_length' / Const(b'\x02\x15'),
    'uuid' / Array(16, Byte),
    'major' / Int16ub,
    'minor' / Int16ub,
    'tx_power' / Int8sl,
)

CV: ContextVar['BaseScanner'] = ContextVar('scanner.BaseScanner')

LOGGER = logging.getLogger(__name__)


class BaseScanner(ABC):

    @abstractmethod
    async def scan(self, duration: float) -> list[TiltMessage]:
        """
        Scans for given duration, and returns a single message
        for each detected device.
        """


class TiltScanner(BaseScanner):

    def __init__(self) -> None:
        self._scanner = BleakScanner(self._callback)
        self._scan_interval = 1
        self._prev_num_messages = 0
        self._events: dict[str, parser.TiltEvent] = {}

    def _callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        try:
            mac = device.address
            apple_data = advertisement_data.manufacturer_data[const.APPLE_VID]
            packet = BEACON_STRUCT.parse(apple_data)
            uuid = str(UUID(bytes=bytes(packet.uuid)))

            if uuid not in const.TILT_UUID_COLORS.keys():
                return

            LOGGER.debug(f'Recv {mac=} {uuid=}, {packet.major=}, {packet.minor=}')
            self._events[mac] = TiltEvent(mac=mac,
                                          uuid=uuid,
                                          major=packet.major,
                                          minor=packet.minor,
                                          txpower=packet.tx_power,
                                          rssi=advertisement_data.rssi)

        except KeyError:
            pass  # Apple vendor ID not found
        except ConstError:
            pass  # Not an iBeacon

    async def scan(self, duration: float) -> list[TiltMessage]:
        async with self._scanner:
            await asyncio.sleep(duration)

        messages = parser.CV.get().parse(list(self._events.values()))
        self._events.clear()
        return messages


class Simulation:

    def __init__(self, simulated: str) -> None:
        self.uuid = next((
            uuid
            for uuid, color in const.TILT_UUID_COLORS.items()
            if color.upper() == simulated.upper()
        ), '')
        self.mac = self.uuid.replace('-', '').upper()[:12]
        LOGGER.info(f'Simulation: {simulated}={self.mac}')

        self.interval = 1
        self.temp_f = 68
        self.raw_sg = 1050
        self.rssi = -80

    def update(self) -> TiltEvent:
        self.temp_f += uniform(-2, 2)
        self.raw_sg += uniform(-10, 10)
        self.rssi += uniform(-1, 1)

        return TiltEvent(mac=self.mac,
                         uuid=self.uuid,
                         major=int(self.temp_f),
                         minor=int(self.raw_sg),
                         txpower=0,
                         rssi=int(self.rssi))


class SimulatedScanner(BaseScanner):

    def __init__(self) -> None:
        config = utils.get_config()
        self._simulations = [Simulation(simulated)
                             for simulated in config.simulate]

    async def scan(self, duration: float) -> list[TiltMessage]:
        await asyncio.sleep(duration)
        events = [sim.update() for sim in self._simulations]
        messages = parser.CV.get().parse(events)
        return messages


def setup():
    config = utils.get_config()

    if config.simulate:
        CV.set(SimulatedScanner())
    else:
        CV.set(TiltScanner())
