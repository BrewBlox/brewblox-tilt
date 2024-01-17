"""
Tests brewblox_tilt.broadcaster
"""

from contextlib import AsyncExitStack, asynccontextmanager
from unittest.mock import ANY, Mock

import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from starlette.testclient import TestClient

from brewblox_tilt import broadcaster, mqtt, parser, scanner
from brewblox_tilt.stored import calibration, devices


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mqtt.lifespan())
        yield


@pytest.fixture
def app(tempfiles) -> FastAPI:
    mqtt.setup()
    calibration.setup()
    devices.setup()
    parser.setup()
    scanner.setup()
    app = FastAPI(lifespan=lifespan)
    return app


@pytest.fixture
def m_publish(app: FastAPI, mocker: MockerFixture) -> Mock:
    m = mocker.spy(mqtt.CV.get(), 'publish')
    return m


async def test_run(client: TestClient, m_publish: Mock):
    bc = broadcaster.Broadcaster()
    await bc.run()

    # Generic state, history, and two devices
    assert m_publish.call_count == 4

    m_publish.assert_any_call('brewcast/state/tilt',
                              {
                                  'key': 'tilt',
                                  'type': 'Tilt.state.service',
                                  'timestamp': ANY,
                              },
                              retain=True)

    m_publish.assert_any_call('brewcast/history/tilt',
                              {
                                  'key': 'tilt',
                                  'data': {
                                      'Pink': {
                                          'temperature[degF]': ANY,
                                          'temperature[degC]': ANY,
                                          'specificGravity': ANY,
                                          'plato[degP]': ANY,
                                          'rssi[dBm]': ANY,
                                      },
                                      'Orange': {
                                          'temperature[degF]': ANY,
                                          'temperature[degC]': ANY,
                                          'specificGravity': ANY,
                                          'plato[degP]': ANY,
                                          'rssi[dBm]': ANY,
                                      }
                                  }
                              })

    m_publish.assert_any_call('brewcast/state/tilt/Pink/A495BB80C5B1',
                              {
                                  'key': 'tilt',
                                  'type': 'Tilt.state',
                                  'timestamp': ANY,
                                  'color': 'Pink',
                                  'mac': 'A495BB80C5B1',
                                  'name': 'Pink',
                                  'data': {
                                      'temperature[degF]': ANY,
                                      'temperature[degC]': ANY,
                                      'specificGravity': ANY,
                                          'plato[degP]': ANY,
                                          'rssi[dBm]': ANY,
                                  }
                              },
                              retain=True)

    m_publish.assert_any_call('brewcast/state/tilt/Orange/A495BB50C5B1',
                              {
                                  'key': 'tilt',
                                  'type': 'Tilt.state',
                                  'timestamp': ANY,
                                  'color': 'Orange',
                                  'mac': 'A495BB50C5B1',
                                  'name': 'Orange',
                                  'data': {
                                      'temperature[degF]': ANY,
                                      'temperature[degC]': ANY,
                                      'specificGravity': ANY,
                                          'plato[degP]': ANY,
                                          'rssi[dBm]': ANY,
                                  }
                              },
                              retain=True)
