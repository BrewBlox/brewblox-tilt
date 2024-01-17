import time
import traceback
from functools import lru_cache

from .models import ServiceConfig


@lru_cache
def get_config() -> ServiceConfig:  # pragma: no cover
    return ServiceConfig()


def time_ms():
    return time.time_ns() // 1000000


def strex(ex: Exception, tb=False):
    """
    Generic formatter for exceptions.
    A formatted traceback is included if `tb=True`.
    """
    msg = f'{type(ex).__name__}({str(ex)})'
    if tb:
        trace = ''.join(traceback.format_exception(None, ex, ex.__traceback__))
        return f'{msg}\n\n{trace}'
    else:
        return msg
