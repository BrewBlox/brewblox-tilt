"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""


import json
import logging
from io import FileIO
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Generator

import pytest
from fastapi import FastAPI
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from pytest_docker.plugin import Services as DockerServices
from starlette.testclient import TestClient

from brewblox_tilt import app_factory, const, utils
from brewblox_tilt.models import ServiceConfig

LOGGER = logging.getLogger(__name__)


class TestConfig(ServiceConfig):
    """
    An override for ServiceConfig that only uses
    settings provided to __init__()

    This makes tests independent from env values
    and the content of .appenv
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


@pytest.fixture(autouse=True)
def config(monkeypatch: pytest.MonkeyPatch,
           docker_services: DockerServices,
           ) -> Generator[ServiceConfig, None, None]:
    cfg = TestConfig(
        debug=True,
        mqtt_host='localhost',
        mqtt_port=docker_services.port_for('mqtt', 1883),
        scan_duration=0.1,
        simulate=['Pink', 'Orange'],
    )
    monkeypatch.setattr(utils, 'get_config', lambda: cfg)
    yield cfg


@pytest.fixture(scope='session')
def docker_compose_file():
    return Path('./test/docker-compose.yml').resolve()


@pytest.fixture(autouse=True)
def setup_logging(config):
    app_factory.setup_logging(True)


@pytest.fixture
def app() -> FastAPI:
    """
    Override this in test modules to bootstrap required dependencies.

    IMPORTANT: This must NOT be an async fixture.
    Contextvars assigned in async fixtures are invisible to test functions.
    """
    app = FastAPI()
    return app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url='http://test') as c:
        yield c


@pytest.fixture
def tilt_macs() -> dict:
    return {
        'red': 'AA7F97FC141E',
        'black': 'DD7F97FC141E',
        'purple': 'BB7F97FC141E',
    }


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch) -> TemporaryDirectory:
    d = TemporaryDirectory()
    monkeypatch.setattr(const, 'CONFIG_DIR', Path(d.name))
    yield d


@pytest.fixture
def devices_file(monkeypatch: pytest.MonkeyPatch, tilt_macs: dict) -> FileIO:
    f = NamedTemporaryFile()
    f.write(json.dumps({
        'names': {
            tilt_macs['red']: 'Red',
            tilt_macs['black']: 'Black',
            tilt_macs['purple']: 'Ferment 1 Tilt',
        }
    }).encode())
    f.flush()
    monkeypatch.setattr(const, 'DEVICES_FILE_PATH', Path(f.name))
    yield f


@pytest.fixture
def sgcal_file(monkeypatch: pytest.MonkeyPatch) -> FileIO:
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
    monkeypatch.setattr(const, 'SG_CAL_FILE_PATH', Path(f.name))
    yield f


@pytest.fixture
def tempcal_file(monkeypatch: pytest.MonkeyPatch) -> FileIO:
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
    monkeypatch.setattr(const, 'TEMP_CAL_FILE_PATH', Path(f.name))
    yield f


@pytest.fixture
def tempfiles(monkeypatch: pytest.MonkeyPatch,
              sgcal_file: FileIO,
              tempcal_file: FileIO,
              devices_file: FileIO,
              config_dir: TemporaryDirectory):
    return
