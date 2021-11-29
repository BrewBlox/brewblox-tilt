"""
Tests brewblox_tilt.parser
"""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest

from brewblox_tilt import const, parser

TESTED = parser.__name__

RED_MAC = 'AA7F97FC141E'
PURPLE_MAC = 'BB7F97FC141E'
BLACK_MAC = 'DD7F97FC141E'


@pytest.fixture
def m_sg_file():
    f = NamedTemporaryFile()
    f.writelines([
        f'{s}\n'.encode()
        for s in [
            'Black, 1.000, 2.001',
            'Black, 1.001, 2.002',
            'Black, 1.002, 2.003',
            'BLACK, 1.003, 2.004',
            'Black, 1, Many',
            'Black, Few, 2.005',
            ''
            '"Ferment 1 red", 1.000, 3.010',
            '"Ferment 1 red", 1.001, 3.011',
            '"Ferment 1 red", 1.002, 3.012',
            '"Ferment 1 red", 1.003, 3.013',
            '"Ferment 1 red", 1.004, 3.014',
        ]])
    f.flush()
    yield f


@pytest.fixture
def m_temp_file():
    f = NamedTemporaryFile()
    f.writelines([
        f'{s}\n'.encode()
        for s in [
            'Black, 39,40',
            'Black, 46,48',
            'Black, 54,55',
            'Black, 60,62',
            'Black, 68,70',
            'Black, 76,76',
        ]])
    f.flush()
    yield f


@pytest.fixture
def m_devices_file():
    f = NamedTemporaryFile()
    f.write(json.dumps({'names': {BLACK_MAC: 'Black'}}).encode())
    f.flush()
    yield f


@pytest.fixture
def m_config_dir():
    d = TemporaryDirectory()
    yield d


@pytest.fixture
def m_files(mocker, m_sg_file, m_temp_file, m_devices_file, m_config_dir):
    mocker.patch(TESTED + '.const.CONFIG_DIR', Path(m_config_dir.name))
    mocker.patch(TESTED + '.const.SG_CAL_FILE_PATH', Path(m_sg_file.name))
    mocker.patch(TESTED + '.const.TEMP_CAL_FILE_PATH', Path(m_temp_file.name))
    mocker.patch(TESTED + '.const.DEVICES_FILE_PATH', Path(m_devices_file.name))


def test_calibrator(m_sg_file):
    calibrator = parser.Calibrator(m_sg_file.name)
    assert 'black' in calibrator.cal_polys
    assert 'ferment 1 red' in calibrator.cal_polys
    assert calibrator.cal_polys['black'].order == 3

    cal_black_v = calibrator.calibrated_value(['Dummy', 'Black'], 1.002, 3)
    assert cal_black_v == pytest.approx(2, 0.1)

    cal_red_v = calibrator.calibrated_value(['Ferment 1 red'], 1.002, 3)
    assert cal_red_v == pytest.approx(3, 0.1)

    assert calibrator.calibrated_value(['Dummy'], 1.002, 3) is None


def test_data_parser(app, m_files):
    red_uuid = next((k for k, v in const.TILT_UUID_COLORS.items() if v == 'Red'))
    purple_uuid = next((k for k, v in const.TILT_UUID_COLORS.items() if v == 'Purple'))
    black_uuid = next((k for k, v in const.TILT_UUID_COLORS.items() if v == 'Black'))
    data_parser = parser.EventDataParser(app)
    data_parser.apply_custom_names({RED_MAC: 'Ferment 1 red'})

    messages = data_parser.parse([
        # Valid red - SG calibration data
        parser.TiltEvent(mac=RED_MAC,
                         uuid=red_uuid,
                         major=68,  # temp F
                         minor=1.002*1000,  # raw SG,
                         txpower=0,
                         rssi=-80),
        # Valid black - SG and temp calibration data
        parser.TiltEvent(mac=BLACK_MAC,
                         uuid=black_uuid,
                         major=68,  # temp F
                         minor=1.002*1000,  # raw SG,
                         txpower=0,
                         rssi=-80),
        # Invalid: out of bounds SG
        parser.TiltEvent(mac=RED_MAC,
                         uuid=red_uuid,
                         major=68,  # temp F
                         minor=1.002*1000000,  # raw SG,
                         txpower=0,
                         rssi=-80),
        # Invalid: invalid UUID
        parser.TiltEvent(mac=RED_MAC,
                         uuid='',
                         major=68,  # temp F
                         minor=1.002*1000000,  # raw SG,
                         txpower=0,
                         rssi=-80),
        # Valid purple - no calibration data
        parser.TiltEvent(mac=PURPLE_MAC,
                         uuid=purple_uuid,
                         major=68,  # temp F
                         minor=1.002*1000,  # raw SG,
                         txpower=0,
                         rssi=-80),

    ])
    assert len(messages) == 3

    # Red
    msg = messages[0]
    assert msg.mac == RED_MAC
    assert msg.color == 'Red'
    assert msg.name == 'Ferment 1 red'
    assert msg.data == {
        'temperature[degF]': pytest.approx(68),
        'temperature[degC]': pytest.approx((68-32)*5/9, 0.01),
        'specificGravity': pytest.approx(3.002, 0.1),
        'plato[degP]': pytest.approx(parser.sg_to_plato(3.002), 30),
        'rssi[dBm]': -80,
        # No temp calibration -> no uncalibrated temp values
        'uncalibratedSpecificGravity': pytest.approx(1.002),
        'uncalibratedPlato[degP]': pytest.approx(10, 3),
    }

    # Black
    msg = messages[1]
    assert msg.mac == BLACK_MAC
    assert msg.color == 'Black'
    assert msg.name == 'Black'
    print(msg.data)
    assert msg.data == {
        'temperature[degF]': pytest.approx(70),  # see: calibration values
        'temperature[degC]': pytest.approx((70-32)*5/9, 0.01),
        'specificGravity': pytest.approx(2.002, 0.1),
        'plato[degP]': pytest.approx(parser.sg_to_plato(2.002), 20),
        'rssi[dBm]': -80,
        # All uncalibrated values present
        'uncalibratedSpecificGravity': pytest.approx(1.002),
        'uncalibratedPlato[degP]': pytest.approx(10, 3),
        'uncalibratedTemperature[degF]': pytest.approx(68),
        'uncalibratedTemperature[degC]': pytest.approx((68-32)*5/9, 0.01),
    }

    # Purple
    msg = messages[2]
    assert msg.mac == PURPLE_MAC
    assert msg.color == 'Purple'
    assert msg.name == 'Purple'
    assert msg.data == {
        'temperature[degF]': pytest.approx(68),
        'temperature[degC]': pytest.approx((68-32)*5/9, 0.01),
        'specificGravity': pytest.approx(1.002),
        'plato[degP]': pytest.approx(10, 3),
        'rssi[dBm]': -80,
        # No uncalibrated values
    }
