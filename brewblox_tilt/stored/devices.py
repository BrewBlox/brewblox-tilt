import json
import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .. import const, mqtt, utils

LOGGER = logging.getLogger(__name__)

CV: ContextVar['DeviceConfig'] = ContextVar('metadata.DeviceConfig')


class DeviceConfig:
    def __init__(self, file: Path) -> None:
        self.path = Path(file)
        self.yaml = YAML()
        self.changed = False

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch()
        self.path.chmod(0o666)

        self.device_config: CommentedMap = self.yaml.load(self.path) or CommentedMap()
        self.device_config.setdefault('names', CommentedMap())
        self.device_config.setdefault('sync', CommentedSeq())

        with self.autocommit():
            if not self.sync:
                self.sync.append({
                    'type': 'TempSensorExternal',
                    'tilt': 'ExampleTilt',
                    'service': 'example-spark-service',
                    'block': 'Example Block Name'
                })
                self.changed = True

            for mac, name in list(self.names.items()):
                if not re.match(const.DEVICE_NAME_PATTERN, name):
                    sanitized = re.sub(const.INVALID_NAME_CHAR_PATTERN, '_', name) or 'Unknown'
                    LOGGER.warning(f'Sanitizing invalid device name: {mac=} {name=}, {sanitized=}.')
                    self.names[mac] = sanitized
                    self.changed = True

        LOGGER.info(f'Device config loaded from `{self.path}`: {str(dict(self.names))}')

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

    @property
    def names(self) -> dict[str, str]:
        return self.device_config['names']

    @property
    def sync(self) -> list[dict[str, str]]:
        return self.device_config['sync']

    @contextmanager
    def autocommit(self):
        try:
            yield
        finally:
            if self.changed:
                self.yaml.dump(self.device_config, self.path)
                self.changed = False

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


def setup():
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()
    CV.set(DeviceConfig(const.DEVICES_FILE_PATH))

    @mqtt_client.subscribe(f'brewcast/tilt/{config.name}/names')
    async def on_names_change(client, topic, payload, qos, properties):
        devconfig = CV.get()
        with devconfig.autocommit():
            devconfig.apply_custom_names(json.loads(payload))
