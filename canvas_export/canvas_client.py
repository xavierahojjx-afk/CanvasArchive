from __future__ import annotations

import logging
from typing import Any

import requests
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings, load_settings

logger = logging.getLogger(__name__)

_NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)

_RETRY_HTTP_CODES = ("429", "500", "502", "503", "504")


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, _NETWORK_ERRORS):
        return True
    if isinstance(exc, CanvasException):
        msg = str(exc)
        return any(code in msg for code in _RETRY_HTTP_CODES)
    return False


canvas_retry = retry(
    retry=retry_if_exception(_should_retry),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)


def get_canvas(settings: Settings | None = None) -> Canvas:
    settings = settings or load_settings()
    return Canvas(settings.canvas_base_url, settings.canvas_token)


@canvas_retry
def verify_token(canvas: Canvas | None = None) -> dict[str, Any]:
    """Hit /users/self via canvasapi and return key user fields."""
    canvas = canvas or get_canvas()
    user = canvas.get_current_user()
    return {
        "id": getattr(user, "id", None),
        "name": getattr(user, "name", None),
        "short_name": getattr(user, "short_name", None),
        "login_id": getattr(user, "login_id", None),
        "primary_email": getattr(user, "primary_email", None),
    }
