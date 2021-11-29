"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""


import logging

import pytest
from brewblox_service import brewblox_logger, features, service

from brewblox_tilt.__main__ import create_parser

LOGGER = brewblox_logger(__name__)


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.captureWarnings(True)


@pytest.fixture
def app_config() -> dict:
    return {
        'name': 'test_app',
        'host': 'localhost',
        'port': 1234,
        'debug': False,
        'lower_bound': 0.5,
        'upper_bound': 2,
        'inactive_scan_interval': 5,
        'active_scan_interval': 20,
        'simulate': None,
    }


@pytest.fixture
def sys_args(app_config) -> list:
    return [str(v) for v in [
        'app_name',
        '--name', app_config['name'],
        '--host', app_config['host'],
        '--port', app_config['port'],
        '--lower-bound', app_config['lower_bound'],
        '--upper-bound', app_config['upper_bound'],
        '--inactive-scan-interval', app_config['inactive_scan_interval'],
        '--active-scan-interval', app_config['active_scan_interval'],
    ]]


@pytest.fixture
def app(sys_args):
    parser = create_parser('default')
    app = service.create_app(parser=parser, raw_args=sys_args[1:])
    return app


@pytest.fixture
async def client(app, aiohttp_client, aiohttp_server):
    """Allows patching the app or aiohttp_client before yielding it.

    Any tests wishing to add custom behavior to app can override the fixture
    """
    LOGGER.debug('Available features:')
    for name, impl in app.get(features.FEATURES_KEY, {}).items():
        LOGGER.debug(f'Feature "{name}" = {impl}')
    LOGGER.debug(app.on_startup)

    return await aiohttp_client(await aiohttp_server(app))
