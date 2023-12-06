import csv
import json
import logging
from contextvars import ContextVar
from pathlib import Path

import numpy as np
from pint import UnitRegistry

from . import const, mqtt, stored, utils
from .models import TiltEvent, TiltMessage, TiltTemperatureSync

_UREG: ContextVar['UnitRegistry'] = ContextVar('parser.UnitRegistry')
CV: ContextVar['EventDataParser'] = ContextVar('parser.EventDataParser')

LOGGER = logging.getLogger(__name__)


def deg_f_to_c(value_f: float | None) -> float | None:
    if value_f is None:
        return None
    ureg = _UREG.get()
    value_c = ureg.Quantity(value_f, ureg.degF).to('degC').magnitude
    return round(value_c, 2)


def sg_to_plato(sg: float | None) -> float | None:
    if sg is None:
        return None
    # From https://www.brewersfriend.com/plato-to-sg-conversion-chart/
    plato = ((-1 * 616.868)
             + (1111.14 * sg)
             - (630.272 * sg**2)
             + (135.997 * sg**3))
    return round(plato, 3)


class Calibrator():
    def __init__(self, file: Path | str) -> None:
        self.cal_polys: dict[str, np.poly1d] = {}
        self.keys: set[str] = set()
        self.path = Path(file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch()
        self.path.chmod(0o666)

        cal_tables = {}

        # Load calibration CSV
        with open(self.path, newline='') as f:
            reader = csv.reader(f, delimiter=',')
            for line in reader:
                key = None  # MAC or name
                uncal = None
                cal = None

                key = line[0].strip().lower()

                try:
                    uncal = float(line[1].strip())
                except ValueError:
                    LOGGER.warning(f'Uncalibrated value `{line[1]}` not a float. Ignoring line.')
                    continue

                try:
                    cal = float(line[2].strip())
                except ValueError:
                    LOGGER.warning(f'Calibrated value `{line[2]}` not a float. Ignoring line.')
                    continue

                self.keys.add(key)
                data = cal_tables.setdefault(key, {
                    'uncal': [],
                    'cal': [],
                })
                data['uncal'].append(uncal)
                data['cal'].append(cal)

        # Use polyfit to fit a cubic polynomial curve to calibration values
        # Then create a polynomical from the values produced by polyfit
        for key, data in cal_tables.items():
            x = np.array(data['uncal'])
            y = np.array(data['cal'])
            z = np.polyfit(x, y, 3)
            self.cal_polys[key] = np.poly1d(z)

        LOGGER.info(f'Calibration values loaded from `{self.path}`: keys={*self.cal_polys.keys(),}')

    def calibrated_value(self, key_candidates: list[str], value: float, ndigits=0) -> float | None:
        # Use polynomials calculated above to calibrate values
        # Both MAC and device name are valid keys in calibration files
        # Check whether any of the given keys is present
        for key in [k.lower() for k in key_candidates]:
            if key in self.cal_polys:
                return round(self.cal_polys[key](value), ndigits)
        return None


class EventDataParser():
    def __init__(self):
        config = utils.get_config()
        self.lower_bound = config.lower_bound
        self.upper_bound = config.upper_bound

        self.devconfig = stored.DeviceConfig(const.DEVICES_FILE_PATH)
        self.session_macs: set[str] = set()
        self.sg_cal = Calibrator(const.SG_CAL_FILE_PATH)
        self.temp_cal = Calibrator(const.TEMP_CAL_FILE_PATH)

    def _decode_event_data(self, event: TiltEvent) -> dict | None:
        """
        Extract raw temp and SG values from the event data object.

        Returns None if event data is invalid.
        """
        # The Tilt color is identified by the UUID field in the iBeacon packet
        color = const.TILT_UUID_COLORS.get(event.uuid, None)

        if color is None:
            return None

        temp_f = event.major
        sg = event.minor

        # The Tilt Pro has an extra decimal for both temp and SG
        # We can do a boundary check to find out
        is_tilt_pro = sg > 5000

        if is_tilt_pro:
            sg = sg / 10000
            temp_f = temp_f / 10
        else:
            sg = sg / 1000

        # The Tilt sometimes broadcasts SG values in the millions
        # Prevent data pollution by discarding values that are physically impossible
        if sg < self.lower_bound or sg > self.upper_bound:
            LOGGER.warning(f'Discarding Tilt event for {color}/{event.mac}. ' +
                           f'SG={sg} bounds=[{self.lower_bound}, {self.upper_bound}]')
            return None

        return {
            'color': color,
            'temp_f': temp_f,
            'sg': sg,
            'is_pro': is_tilt_pro,
        }

    def _parse_event(self, event: TiltEvent) -> TiltMessage | None:
        """
        Adds raw and calibrated values for a single Tilt event to the combined `message` object.

        If the event is invalid, `message` is returned unchanged.
        """
        decoded = self._decode_event_data(event)
        if decoded is None:
            return None

        color = decoded['color']
        mac = event.mac.strip().replace(':', '').upper()
        name = self.devconfig.lookup(mac, color)

        if mac not in self.session_macs:
            self.session_macs.add(mac)
            LOGGER.info(f'Tilt detected: {mac=}, {color=}, {name=}')

        raw_temp_f = decoded['temp_f']
        raw_temp_c = deg_f_to_c(raw_temp_f)

        is_pro = decoded['is_pro']
        temp_digits = 1 if is_pro else 0
        sg_digits = 4 if is_pro else 3

        cal_temp_f = self.temp_cal.calibrated_value([mac, name],
                                                    raw_temp_f,
                                                    temp_digits)
        cal_temp_c = deg_f_to_c(cal_temp_f)

        raw_sg = decoded['sg']
        cal_sg = self.sg_cal.calibrated_value([mac, name],
                                              raw_sg,
                                              sg_digits)

        raw_plato = sg_to_plato(raw_sg)
        cal_plato = sg_to_plato(cal_sg)

        data = {
            'temperature[degF]': raw_temp_f,
            'temperature[degC]': raw_temp_c,
            'specificGravity': raw_sg,
            'plato[degP]': raw_plato,
            'rssi[dBm]': event.rssi,
        }

        # If calibrated values are present, they become the default
        # Uncalibrated values are only present if calibrated values are also present
        if cal_temp_f is not None:
            data['temperature[degF]'] = cal_temp_f
            data['uncalibratedTemperature[degF]'] = raw_temp_f
        if cal_temp_c is not None:
            data['temperature[degC]'] = cal_temp_c
            data['uncalibratedTemperature[degC]'] = raw_temp_c
        if cal_sg is not None:
            data['specificGravity'] = cal_sg
            data['uncalibratedSpecificGravity'] = raw_sg
        if cal_plato is not None:
            data['plato[degP]'] = cal_plato
            data['uncalibratedPlato[degP]'] = raw_plato

        sync: list[TiltTemperatureSync] = []

        for src in self.devconfig.sync:
            sync_tilt = src.get('tilt')
            sync_type = src.get('type')
            sync_service = src.get('service')
            sync_block = src.get('block')

            if sync_tilt != name \
                    or not sync_type \
                    or not sync_service \
                    or not sync_block:
                continue

            sync.append(TiltTemperatureSync(
                type=sync_type,
                service=sync_service,
                block=sync_block,
            ))

        return TiltMessage(name=name,
                           mac=mac,
                           color=color,
                           data=data,
                           sync=sync)

    def parse(self, events: list[TiltEvent]) -> list[TiltMessage]:
        """
        Converts a list of Tilt events into a list of Tilt message.
        Invalid events are excluded.
        """
        messages = [self._parse_event(evt) for evt in events]
        self.devconfig.commit()
        return [msg for msg in messages if msg is not None]

    def apply_custom_names(self, names: dict[str, str]) -> None:
        self.devconfig.apply_custom_names(names)
        self.devconfig.commit()


def setup():
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()

    _UREG.set(UnitRegistry())
    CV.set(EventDataParser())

    @mqtt_client.subscribe(f'brewcast/tilt/{config.name}/names')
    async def on_names_change(client, topic, payload, qos, properties):
        CV.get().apply_custom_names(json.loads(payload))
