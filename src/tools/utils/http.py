"""HTTP utilities - rate limiting, smart retries, and robot checks.

The HTTP layer retries only transient errors:
- Connection errors, read timeouts, HTTP 429, HTTP 5xx

Terminal errors (403, 404, 400, etc.) are NOT retried — these indicate
bot protection or missing resources, not transient failures.
"""

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.config import RATE_LIMIT_INTERVAL, REQUEST_TIMEOUT, USER_AGENT
from src.config.logging import get_logger
from src.tools.logging import log_tool_call

logger = get_logger(__name__)

_last_request_time: float = 0.0
_robot_parsers: dict[str, RobotFileParser] = {}

# Terminal HTTP status codes - do not retry these
_TERMINAL_STATUS_CODES = {400, 401, 403, 404, 405, 410, 451}


def _should_retry(exc: Exception) -> bool:
    """Determine if an exception is worth retrying.

    Retries on:
    - Connection errors (server may be temporarily down)
    - Read timeouts (server is slow)
    - HTTP 429 (rate limited)
    - HTTP 5xx (server error)

    Does NOT retry on:
    - HTTP 4xx (client errors like 403, 404 - these are permanent)
    """
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return True
        if status >= 500:
            return True
        return False
    return False


def rate_limit() -> None:
    """Enforce minimum interval between requests."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < RATE_LIMIT_INTERVAL:
        time.sleep(RATE_LIMIT_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def can_fetch(url: str, user_agent: str = "*") -> bool:
    """Check if a URL is allowed by robots.txt."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    if base_url not in _robot_parsers:
        rp = RobotFileParser()
        robots_url = f"{base_url}/robots.txt"
        try:
            rp.set_url(robots_url)
            rp.read()
            _robot_parsers[base_url] = rp
        except Exception:
            logger.debug("Could not fetch robots.txt for %s, allowing", base_url)
            return True

    rp = _robot_parsers[base_url]
    can = rp.can_fetch(user_agent, url)
    if not can:
        logger.info("robots.txt disallows fetching: %s", url)
    return can


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_should_retry),
)
@log_tool_call
def http_get(url: str, timeout: float = REQUEST_TIMEOUT) -> httpx.Response:
    """HTTP GET with retry, rate limiting, and User-Agent.

    Retries on transient errors (connection, timeout, 429, 5xx).
    Does NOT retry on 4xx client errors (403, 404, etc.).
    """
    rate_limit()
    response = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response
