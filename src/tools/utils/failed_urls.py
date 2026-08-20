"""Shared failed URL tracker with TTL expiry.

Prevents retrying URLs that returned 403/bot-detection across all rows
in the same process. Entries expire after FAILED_URL_TTL seconds (default: 300s)
to allow retries after temporary rate limits lift.

Provides FailedURLTracker singleton shared across all rows in a pipeline run.
"""

from __future__ import annotations

import time

from src.config import FAILED_URL_TTL
from src.config.logging import get_logger

logger = get_logger(__name__)


class FailedURLTracker:
    """TTL-based tracker for failed URLs.

    Entries expire after ``ttl`` seconds, allowing retries after
    temporary rate limits or bot protection cooldowns.
    """

    def __init__(self, ttl: float = FAILED_URL_TTL) -> None:
        self._urls: dict[str, float] = {}  # url -> timestamp
        self._ttl = ttl

    def add(self, url: str) -> None:
        """Record a URL as failed."""
        self._urls[url] = time.monotonic()

    def is_failed(self, url: str) -> bool:
        """Check if a URL is currently marked as failed (not expired)."""
        if url not in self._urls:
            return False
        ts = self._urls[url]
        if time.monotonic() - ts >= self._ttl:
            del self._urls[url]
            logger.debug("Failed URL TTL expired, allowing retry: %s", url)
            return False
        return True

    def get_all(self) -> set[str]:
        """Return all currently failed (non-expired) URLs."""
        now = time.monotonic()
        expired = [url for url, ts in self._urls.items() if now - ts >= self._ttl]
        for url in expired:
            del self._urls[url]
        return set(self._urls.keys())

    def load(self, urls: list[str]) -> None:
        """Load URLs into the tracker (e.g., from state)."""
        now = time.monotonic()
        for url in urls:
            if url not in self._urls:
                self._urls[url] = now

    def clear(self) -> None:
        """Clear all tracked URLs."""
        self._urls.clear()

    def __len__(self) -> int:
        return len(self._urls)

    def __contains__(self, url: str) -> bool:
        return self.is_failed(url)


# Module-level singleton — shared across all rows in the same process.
_failed_url_tracker = FailedURLTracker()


def get_failed_url_tracker() -> FailedURLTracker:
    """Return the module-level failed URL tracker singleton."""
    return _failed_url_tracker
