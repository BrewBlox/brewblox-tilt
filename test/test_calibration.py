"""
Tests brewblox_tilt.stored.calibration
"""

import pytest

from brewblox_tilt.stored import calibration

TESTED = calibration.__name__


@pytest.fixture(autouse=True)
def setup(tempfiles):
    calibration.setup()


def test_calibrator():
    calibrator = calibration.SG_CAL.get()
    assert 'black' in calibrator.cal_polys
    assert 'ferment 1 red' in calibrator.cal_polys
    assert calibrator.cal_polys['black'].order == 3

    cal_black_v = calibrator.calibrated_value(['Dummy', 'Black'], 1.002, 3)
    assert cal_black_v == pytest.approx(2, 0.1)

    cal_red_v = calibrator.calibrated_value(['Ferment 1 red'], 1.002, 3)
    assert cal_red_v == pytest.approx(3, 0.1)

    assert calibrator.calibrated_value(['Dummy'], 1.002, 3) is None
