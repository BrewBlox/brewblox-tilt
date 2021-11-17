import re
from pathlib import Path
from typing import Union

from brewblox_service import brewblox_logger
from ruamel.yaml import YAML

from brewblox_tilt import const

LOGGER = brewblox_logger(__name__)


class DeviceNameRegistry():
    def __init__(self, file: Union[Path, str]) -> None:
        self.path = Path(file)
        self.yaml = YAML()
        self.changed = False
        self.devices = {}

        self.path.touch()
        self.devices = self.yaml.load(self.path) or {}

        if 'names' not in self.devices:
            self.devices['names'] = {}
            self.changed = True

        LOGGER.info(f'Device names loaded from `{self.path}`: '
                    + str(dict(self.devices['names'])))

    @property
    def names(self) -> dict[str, str]:
        return self.devices['names']

    def _assign(self, color: str) -> str:
        used: set[str] = set(self.names.values())
        if color not in used:
            return color

        idx = 1
        while idx < 1000:
            idx += 1
            name = f'{color}-{idx}'
            if name not in used:
                return name

        # Escape hatch for bugs
        # If we have >1000 entries for a given color, something went wrong
        raise RuntimeError('Name increment attempts exhausted')  # pragma: no cover

    def lookup(self, mac: str, color: str) -> str:
        if not re.match(const.NORMALIZED_MAC_PATTERN, mac):
            raise ValueError(f'{mac} is not a normalized device MAC address.')

        name = self.names.get(mac)
        if name:
            return name
        else:
            name = self._assign(color)
            self.names[mac] = name
            self.changed = True
            LOGGER.info(f'New Tilt added: {mac}={name}')
            return name

    def apply_custom_names(self, names: dict[str, str]):
        for mac, name in names.items():
            name = str(name)
            if not re.match(const.NORMALIZED_MAC_PATTERN, mac):
                LOGGER.error(f'Failed to set {mac}={name}: {mac} is not a normalized device MAC address.')
            elif not re.match(const.DEVICE_NAME_PATTERN, name):
                LOGGER.error(f'Failed to set {mac}={name}: {name} is not a valid device name.')
            elif name in self.names.values():
                LOGGER.error(f'Failed to set {mac}={name}: {name} is already in use.')
            else:
                LOGGER.info(f'Device name set: {mac}={name}')
                self.names[mac] = name
                self.changed = True

    def commit(self):
        if self.changed:
            self.yaml.dump(self.devices, self.path)
            self.changed = False
