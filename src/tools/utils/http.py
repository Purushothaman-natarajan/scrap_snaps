"""HTTP utilities - rate limiting, retries, and robot checks."""

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import RATE_LIMIT_INTERVAL, REQUEST_TIMEOUT, USER_AGENT
from src.config.logging import get_logger
from src.tools.logging import log_tool_call

logger = get_logger(__name__)

_last_request_time: float = 0.0
_robot_parsers: dict[str, RobotFileParser] = {}


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
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)),
)
@log_tool_call
def http_get(url: str, timeout: float = REQUEST_TIMEOUT) -> httpx.Response:
    """HTTP GET with retry, rate limiting, and User-Agent."""
    rate_limit()
    response = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response
