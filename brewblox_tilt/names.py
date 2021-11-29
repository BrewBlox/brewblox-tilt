import re
from pathlib import Path
from typing import Union

from brewblox_service import brewblox_logger
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from brewblox_tilt import const

LOGGER = brewblox_logger(__name__)


class DeviceNameRegistry():
    def __init__(self, file: Union[Path, str]) -> None:
        self.path = Path(file)
        self.yaml = YAML()
        self.changed = False
        self.devices = {}

        self.path.touch()
        self.path.chmod(0o666)

        self.devices: CommentedMap = self.yaml.load(self.path) or CommentedMap()
        self.devices.setdefault('names', CommentedMap())

        for mac, name in list(self.names.items()):
            if not re.match(const.DEVICE_NAME_PATTERN, name):
                sanitized = re.sub(const.INVALID_NAME_CHAR_PATTERN, '_', name) or 'Unknown'
                LOGGER.warning(f'Sanitizing invalid device name: {mac=} {name=}, {sanitized=}.')
                self.names[mac] = sanitized
                self.changed = True

        LOGGER.info(f'Device names loaded from `{self.path}`: {str(dict(self.names))}')

    @property
    def names(self) -> dict[str, str]:
        return self.devices['names']

    def _assign(self, base_name: str) -> str:
        used: set[str] = set(self.names.values())
        if base_name not in used:
            return base_name

        idx = 1
        while idx < 1000:
            idx += 1
            name = f'{base_name}-{idx}'
            if name not in used:
                return name

        # Escape hatch for bugs
        # If we have >1000 entries for a given base name, something went wrong
        raise RuntimeError('Name increment attempts exhausted')  # pragma: no cover

    def lookup(self, mac: str, base_name: str) -> str:
        if not re.match(const.NORMALIZED_MAC_PATTERN, mac):
            raise ValueError(f'{mac} is not a normalized device MAC address.')

        name = self.names.get(mac)
        if name:
            return name
        else:
            name = self._assign(base_name)
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
            else:
                LOGGER.info(f'Device name set: {mac}={name}')
                self.names[mac] = name
                self.changed = True

    def commit(self):
        if self.changed:
            self.yaml.dump(self.devices, self.path)
            self.changed = False
