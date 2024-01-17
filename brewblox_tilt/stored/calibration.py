import csv
import logging
from contextvars import ContextVar
from pathlib import Path

import numpy as np

from .. import const

LOGGER = logging.getLogger(__name__)

SG_CAL: ContextVar['Calibrator'] = ContextVar('calibration.Calibrator.sg')
TEMP_CAL: ContextVar['Calibrator'] = ContextVar('calibration.Calibrator.temp')


class Calibrator:
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


def setup():
    SG_CAL.set(Calibrator(const.SG_CAL_FILE_PATH))
    TEMP_CAL.set(Calibrator(const.TEMP_CAL_FILE_PATH))
