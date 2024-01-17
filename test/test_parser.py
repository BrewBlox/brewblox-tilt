"""
Tests brewblox_tilt.parser
"""

import pytest

from brewblox_tilt import const, mqtt, parser
from brewblox_tilt.stored import calibration, devices

TESTED = parser.__name__


@pytest.fixture(autouse=True)
def setup(tempfiles):
    mqtt.setup()
    calibration.setup()
    devices.setup()
    parser.setup()


def test_data_parser(tilt_macs: dict):
    data_parser = parser.CV.get()
    device_config = devices.CV.get()

    red_mac = tilt_macs['red']
    black_mac = tilt_macs['black']
    purple_mac = tilt_macs['purple']

    red_uuid = next((k for k, v in const.TILT_UUID_COLORS.items() if v == 'Red'))
    purple_uuid = next((k for k, v in const.TILT_UUID_COLORS.items() if v == 'Purple'))
    black_uuid = next((k for k, v in const.TILT_UUID_COLORS.items() if v == 'Black'))

    device_config.apply_custom_names({red_mac: 'Ferment 1 red'})

    messages = data_parser.parse([
        # Valid red - SG calibration data
        parser.TiltEvent(mac=red_mac,
                         uuid=red_uuid,
                         major=68,  # temp F
                         minor=1.002*1000,  # raw SG,
                         txpower=0,
                         rssi=-80),
        # Valid black - SG and temp calibration data
        parser.TiltEvent(mac=black_mac,
                         uuid=black_uuid,
                         major=68,  # temp F
                         minor=1.002*1000,  # raw SG,
                         txpower=0,
                         rssi=-80),
        # Invalid: out of bounds SG
        parser.TiltEvent(mac=red_mac,
                         uuid=red_uuid,
                         major=68,  # temp F
                         minor=1.002*1000000,  # raw SG,
                         txpower=0,
                         rssi=-80),
        # Invalid: invalid UUID
        parser.TiltEvent(mac=red_mac,
                         uuid='',
                         major=68,  # temp F
                         minor=1.002*1000000,  # raw SG,
                         txpower=0,
                         rssi=-80),
        # Valid purple - no calibration data
        parser.TiltEvent(mac=purple_mac,
                         uuid=purple_uuid,
                         major=68,  # temp F
                         minor=1.002*1000,  # raw SG,
                         txpower=0,
                         rssi=-80),

    ])
    assert len(messages) == 3

    # Red
    msg = messages[0]
    assert msg.mac == red_mac
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
    assert msg.mac == black_mac
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
    assert msg.mac == purple_mac
    assert msg.color == 'Purple'
    assert msg.name == 'Ferment 1 Tilt'
    assert msg.data == {
        'temperature[degF]': pytest.approx(68),
        'temperature[degC]': pytest.approx((68-32)*5/9, 0.01),
        'specificGravity': pytest.approx(1.002),
        'plato[degP]': pytest.approx(10, 3),
        'rssi[dBm]': -80,
        # No uncalibrated values
    }
