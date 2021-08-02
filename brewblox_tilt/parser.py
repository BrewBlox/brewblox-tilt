import csv
import os.path
from functools import reduce
from typing import List, Optional

import numpy as np
from brewblox_service import brewblox_logger
from pint import UnitRegistry

from brewblox_tilt import blescan

LOGGER = brewblox_logger(__name__)
ureg = UnitRegistry()
Q_ = ureg.Quantity

SG_CAL_FILE_PATH = '/share/SGCal.csv'
TEMP_CAL_FILE_PATH = '/share/tempCal.csv'
TILT_COLOURS = {
    'a495bb10c5b14b44b5121370f02d74de': 'Red',
    'a495bb20c5b14b44b5121370f02d74de': 'Green',
    'a495bb30c5b14b44b5121370f02d74de': 'Black',
    'a495bb40c5b14b44b5121370f02d74de': 'Purple',
    'a495bb50c5b14b44b5121370f02d74de': 'Orange',
    'a495bb60c5b14b44b5121370f02d74de': 'Blue',
    'a495bb70c5b14b44b5121370f02d74de': 'Yellow',
    'a495bb80c5b14b44b5121370f02d74de': 'Pink'
}


def deg_f_to_c(value_f: Optional[float]) -> Optional[float]:
    if value_f is None:
        return None
    value_c = Q_(value_f, ureg.degF).to('degC').magnitude
    return round(value_c, 2)


def sg_to_plato(sg: Optional[float]) -> Optional[float]:
    if sg is None:
        return None
    # From https://www.brewersfriend.com/plato-to-sg-conversion-chart/
    plato = ((-1 * 616.868)
             + (1111.14 * sg)
             - (630.272 * sg**2)
             + (135.997 * sg**3))
    return round(plato, 3)


class Calibrator():
    def __init__(self, file):
        self.cal_tables = {}
        self.cal_polys = {}
        self.load_file(file)

    def load_file(self, file: str):
        if not os.path.exists(file):
            LOGGER.warning(
                f"Calibration file `{file}` not found. Calibrated values won't be provided.")
            return

        # Load calibration CSV
        with open(file, 'r', newline='') as f:
            reader = csv.reader(f, delimiter=',')
            for line in reader:
                colour = None
                uncal = None
                cal = None

                colour = line[0].strip().capitalize()
                if colour not in TILT_COLOURS.values():
                    LOGGER.warning(f'Unknown tilt colour `{line[0]}`. Ignoring line.')
                    continue

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

                self.cal_tables.setdefault(colour, {
                    'uncal': [],
                    'cal': [],
                })
                self.cal_tables[colour]['uncal'].append(uncal)
                self.cal_tables[colour]['cal'].append(cal)

        # Use polyfit to fit a cubic polynomial curve to calibration values
        # Then create a polynomical from the values produced by polyfit
        for colour in self.cal_tables:
            x = np.array(self.cal_tables[colour]['uncal'])
            y = np.array(self.cal_tables[colour]['cal'])
            z = np.polyfit(x, y, 3)
            self.cal_polys[colour] = np.poly1d(z)

        key_str = ', '.join(self.cal_polys.keys())
        LOGGER.info(f'Calibration file {file} loaded for colours: {key_str}')

    def calibrated_value(self, colour: str, value: float, ndigits=0) -> Optional[float]:
        # Use polynomials calculated above to calibrate values
        if colour in self.cal_polys:
            return round(self.cal_polys[colour](value), ndigits)
        else:
            return None


class EventDataParser():
    def __init__(self, app):
        self.known_tilts = set()
        self.lower_bound = app['config']['lower_bound']
        self.upper_bound = app['config']['upper_bound']

        self.sg_cal = Calibrator(SG_CAL_FILE_PATH)
        self.temp_cal = Calibrator(TEMP_CAL_FILE_PATH)

    def _decode_event_data(self, event: blescan.TiltEventData) -> Optional[dict]:
        """
        Extract raw temp and SG values from the event data object.

        Returns None if event data is invalid.
        """

        # Tilt uses a similar data layout to iBeacons accross manufacturer data
        # hex digits 8 - 50. Digits 8-40 contain the ID of the 'colour' of the
        # device. Digits 40-44 contain the temperature in f as an integer.
        # Digits 44-48 contain the specific gravity * 1000 (i.e. the 'points)
        # as an integer.
        colour = TILT_COLOURS.get(event.uuid, None)

        if colour is None:
            # UUID is not for a Tilt
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

        # Garbled bluetooth packets may result in wildly inaccurate readings
        # We want to discard SG values that are objectively impossible
        if sg < self.lower_bound or sg > self.upper_bound:
            LOGGER.warn(f'Discarding Tilt event for {colour}. SG={sg} bounds=[{self.lowerBound}, {self.upperBound}]')
            return None

        return {
            'colour': colour,
            'temp_f': temp_f,
            'sg': sg,
            'is_pro': is_tilt_pro,
        }

    def _add_parsed_event(self, message: dict, event: blescan.TiltEventData) -> dict:
        """
        Adds raw and calibrated values for a single Tilt event to the combined `message` object.

        If the event is invalid, `message` is returned unchanged.
        """
        decoded = self._decode_event_data(event)
        if decoded is None:
            return message

        colour = decoded['colour']

        if colour not in self.known_tilts:
            self.known_tilts.add(colour)
            LOGGER.info(f'Found Tilt: {colour}')

        raw_temp_f = decoded['temp_f']
        raw_temp_c = deg_f_to_c(raw_temp_f)

        is_pro = decoded['is_pro']
        temp_digits = 1 if is_pro else 0
        sg_digits = 4 if is_pro else 3

        cal_temp_f = self.temp_cal.calibrated_value(colour, raw_temp_f, temp_digits)
        cal_temp_c = deg_f_to_c(cal_temp_f)

        raw_sg = decoded['sg']
        cal_sg = self.sg_cal.calibrated_value(colour, raw_sg, sg_digits)

        raw_plato = sg_to_plato(raw_sg)
        cal_plato = sg_to_plato(cal_sg)

        submessage = {
            'Temperature[degF]': raw_temp_f,
            'Temperature[degC]': raw_temp_c,
            'Specific gravity': raw_sg,
            'Plato[degP]': raw_plato,
            'Signal strength[dBm]': event.rssi,
        }

        if cal_temp_f is not None:
            submessage['Calibrated temperature[degF]'] = cal_temp_f
        if cal_temp_c is not None:
            submessage['Calibrated temperature[degC]'] = cal_temp_c
        if cal_sg is not None:
            submessage['Calibrated specific gravity'] = cal_sg
        if cal_plato is not None:
            submessage['Calibrated plato[degP]'] = cal_plato

        message[colour] = submessage
        return message

    def parse(self, events: List[blescan.TiltEventData]) -> dict:
        """
        Converts a list of Tilt events into a combined message.
        Tilt colour is used as key, and data includes raw and calibrated values.

        If `events` is empty or only includes invalid events, an empty dict is returned.
        """
        message = reduce(self._add_parsed_event, events, {})
        return message
