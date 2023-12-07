"""
Tests brewblox_tilt.config
"""
import json
from io import FileIO
from tempfile import NamedTemporaryFile

import pytest
from pytest_mock import MockerFixture

from brewblox_tilt import mqtt, stored

TESTED = stored.__name__


@pytest.fixture(autouse=True)
def setup(tempfiles):
    mqtt.setup()
    stored.setup()


def default_names():
    # Matches devices from conftest
    return {
        'AA7F97FC141E': 'Red',
        'DD7F97FC141E': 'Black',
        'BB7F97FC141E': 'Ferment 1 Tilt',
    }


def test_load():
    registry = stored.DEVICES.get()
    assert registry.names == default_names()


def test_empty():
    f = NamedTemporaryFile()
    registry = stored.DeviceConfig(f.name)
    assert registry.names == {}


def test_sanitize():
    f = NamedTemporaryFile()
    f.write(json.dumps({
        'names': {
            'DD7F97FC141E': '++Purple ++',
            'EE7F97FC141E': '',
        },
    }).encode())
    f.flush()
    registry = stored.DeviceConfig(f.name)
    assert registry.names == {
        'DD7F97FC141E': '__Purple __',
        'EE7F97FC141E': 'Unknown',
    }


def test_lookup():
    registry = stored.DEVICES.get()
    assert registry.lookup('DD7F97FC141E', '') == 'Black'
    assert registry.lookup('AA7F97FC141E', 'Red') == 'Red'
    assert registry.lookup('AB7F97FC141E', 'Red') == 'Red-2'
    assert registry.lookup('AC7F97FC141E', 'Red') == 'Red-3'
    assert registry.lookup('CC7F97FC141E', 'Pink') == 'Pink'

    assert registry.names == {
        **default_names(),
        'AA7F97FC141E': 'Red',
        'AB7F97FC141E': 'Red-2',
        'AC7F97FC141E': 'Red-3',
        'CC7F97FC141E': 'Pink',
    }

    with pytest.raises(ValueError, match='not a normalized device MAC address'):
        registry.lookup('Dummy', 'Black')


def test_apply_custom_names():
    registry = stored.DEVICES.get()
    registry.apply_custom_names({
        'AA7F97FC141E': 'Red',
        'BB7F97FC141E': 'Red',  # Duplicate name
        'Dummy': 'Dummy',  # Invalid MAC
        'CA7F97FC141E': '+++',  # Invalid name
        'CC7F97FC141E': 'Pink',
        'DD7F97FC141E': 'Pretty Purple',
    })
    assert registry.names == {
        **default_names(),
        'AA7F97FC141E': 'Red',
        'BB7F97FC141E': 'Red',
        'CC7F97FC141E': 'Pink',
        'DD7F97FC141E': 'Pretty Purple',
    }
    assert registry.changed


def test_autocommit(devices_file: FileIO, mocker: MockerFixture):
    registry = stored.DeviceConfig(devices_file.name)
    mocker.patch.object(registry, 'yaml', wraps=registry.yaml)

    with registry.autocommit():
        # add new item
        registry.lookup('FF7F97FC141E', 'Red 2')

        # Changes are not yet committed to file
        registry2 = stored.DeviceConfig(devices_file.name)
        assert registry2.names == default_names()
        assert registry.yaml.dump.call_count == 0

    assert registry.yaml.dump.call_count == 1

    # Changes are committed and present in file
    registry3 = stored.DeviceConfig(devices_file.name)
    assert registry3.names == {
        **default_names(),
        'FF7F97FC141E': 'Red 2',
    }


def test_calibrator():
    calibrator = stored.SG_CAL.get()
    assert 'black' in calibrator.cal_polys
    assert 'ferment 1 red' in calibrator.cal_polys
    assert calibrator.cal_polys['black'].order == 3

    cal_black_v = calibrator.calibrated_value(['Dummy', 'Black'], 1.002, 3)
    assert cal_black_v == pytest.approx(2, 0.1)

    cal_red_v = calibrator.calibrated_value(['Ferment 1 red'], 1.002, 3)
    assert cal_red_v == pytest.approx(3, 0.1)

    assert calibrator.calibrated_value(['Dummy'], 1.002, 3) is None
