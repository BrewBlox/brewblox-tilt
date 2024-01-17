import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pprint import pformat

from fastapi import FastAPI

from . import broadcaster, mqtt, parser, scanner, stored, utils

LOGGER = logging.getLogger(__name__)


def setup_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    unimportant_level = logging.INFO if debug else logging.WARN
    format = '%(asctime)s.%(msecs)03d [%(levelname).1s:%(name)s:%(lineno)d] %(message)s'
    datefmt = '%Y/%m/%d %H:%M:%S'

    logging.basicConfig(level=level, format=format, datefmt=datefmt)
    logging.captureWarnings(True)

    logging.getLogger('gmqtt').setLevel(unimportant_level)
    logging.getLogger('httpx').setLevel(unimportant_level)
    logging.getLogger('httpcore').setLevel(logging.WARN)
    logging.getLogger('uvicorn.access').setLevel(unimportant_level)
    logging.getLogger('uvicorn.error').disabled = True
    logging.getLogger('bleak.backends.bluezdbus.manager').setLevel(unimportant_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOGGER.info(utils.get_config())
    LOGGER.debug('LOGGERS:\n' + pformat(logging.root.manager.loggerDict))

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mqtt.lifespan())
        await stack.enter_async_context(broadcaster.lifespan())
        yield


def create_app() -> FastAPI:
    config = utils.get_config()
    setup_logging(config.debug)

    # Call setup functions for modules
    mqtt.setup()
    stored.setup()
    parser.setup()
    scanner.setup()

    app = FastAPI(lifespan=lifespan)
    return app
