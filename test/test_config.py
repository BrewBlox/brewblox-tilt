"""
Tests brewblox_tilt.config
"""
import json
from tempfile import NamedTemporaryFile

import pytest

from brewblox_tilt import config

TESTED = config.__name__


def default_names():
    return {
        'DD7F97FC141E': 'Purple',
        'EE7F97FC141E': 'Ferment 1 tilt',
    }


@pytest.fixture
def m_file():
    f = NamedTemporaryFile()
    f.write(json.dumps({'names': default_names()}).encode())
    f.flush()
    return f


def test_load(m_file):
    registry = config.DeviceConfig(m_file.name)
    assert registry.names == default_names()


def test_empty():
    f = NamedTemporaryFile()
    registry = config.DeviceConfig(f.name)
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
    registry = config.DeviceConfig(f.name)
    assert registry.names == {
        'DD7F97FC141E': '__Purple __',
        'EE7F97FC141E': 'Unknown',
    }


def test_lookup(m_file):
    registry = config.DeviceConfig(m_file.name)
    assert registry.lookup('DD7F97FC141E', '') == 'Purple'
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


def test_apply_custom_names(m_file):
    registry = config.DeviceConfig(m_file.name)
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


def test_commit(m_file, mocker):
    registry = config.DeviceConfig(m_file.name)
    mocker.patch.object(registry, 'yaml', wraps=registry.yaml)
    registry.lookup('AA7F97FC141E', 'Red')

    # Changes are not yet committed to file
    registry2 = config.DeviceConfig(m_file.name)
    assert registry2.names == default_names()

    registry.commit()
    registry.commit()
    assert registry.yaml.dump.call_count == 1

    # Changes are committed and present in file
    registry3 = config.DeviceConfig(m_file.name)
    assert registry3.names == {
        **default_names(),
        'AA7F97FC141E': 'Red',
    }
