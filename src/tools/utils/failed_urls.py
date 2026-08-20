"""Shared failed URL tracker with TTL expiry and disk persistence.

Prevents retrying URLs that returned 403/bot-detection across all rows
in the same process. Entries expire after FAILED_URL_TTL seconds (default: 300s)
to allow retries after temporary rate limits lift.

Persists failed URLs to a JSON file so they survive pipeline restarts.
Provides FailedURLTracker singleton shared across all rows in a pipeline run.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from src.config import FAILED_URL_TTL
from src.config.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_PERSIST_PATH = "data/failed_urls.json"


class FailedURLTracker:
    """TTL-based tracker for failed URLs with disk persistence.

    Entries expire after ``ttl`` seconds, allowing retries after
    temporary rate limits or bot protection cooldowns.
    Failed URLs are persisted to a JSON file so they survive restarts.
    """

    def __init__(self, ttl: float = FAILED_URL_TTL, persist_path: str | None = None) -> None:
        self._urls: dict[str, float] = {}  # url -> wall-clock timestamp (time.time)
        self._ttl = ttl
        self._persist_path = persist_path or _DEFAULT_PERSIST_PATH
        self._load_from_file()

    def add(self, url: str) -> None:
        """Record a URL as failed and persist to disk."""
        self._urls[url] = time.time()
        self._save_to_file()

    def is_failed(self, url: str) -> bool:
        """Check if a URL is currently marked as failed (not expired)."""
        if url not in self._urls:
            return False
        ts = self._urls[url]
        if time.time() - ts >= self._ttl:
            del self._urls[url]
            self._save_to_file()
            logger.debug("Failed URL TTL expired, allowing retry: %s", url)
            return False
        return True

    def get_all(self) -> set[str]:
        """Return all currently failed (non-expired) URLs."""
        now = time.time()
        expired = [url for url, ts in self._urls.items() if now - ts >= self._ttl]
        for url in expired:
            del self._urls[url]
        if expired:
            self._save_to_file()
        return set(self._urls.keys())

    def load(self, urls: list[str]) -> None:
        """Load URLs into the tracker (e.g., from state)."""
        now = time.time()
        changed = False
        for url in urls:
            if url not in self._urls:
                self._urls[url] = now
                changed = True
        if changed:
            self._save_to_file()

    def clear(self) -> None:
        """Clear all tracked URLs and remove persist file."""
        self._urls.clear()
        path = Path(self._persist_path)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass

    def _load_from_file(self) -> None:
        """Load failed URLs from disk, skipping expired entries."""
        path = Path(self._persist_path)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            now = time.time()
            loaded = 0
            for url, ts in data.items():
                if isinstance(ts, (int, float)) and now - ts < self._ttl:
                    self._urls[url] = ts
                    loaded += 1
            if loaded:
                logger.debug("Loaded %d failed URLs from %s", loaded, self._persist_path)
        except Exception as e:
            logger.warning("Failed to load failed URLs from %s: %s", self._persist_path, e)

    def _save_to_file(self) -> None:
        """Persist current failed URLs to disk (atomic)."""
        path = Path(self._persist_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._urls, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception as e:
            logger.warning("Failed to save failed URLs to %s: %s", self._persist_path, e)

    def __len__(self) -> int:
        return len(self._urls)

    def __contains__(self, url: str) -> bool:
        return self.is_failed(url)


# Module-level singleton — shared across all rows in the same process.
_failed_url_tracker = FailedURLTracker()


def get_failed_url_tracker() -> FailedURLTracker:
    """Return the module-level failed URL tracker singleton."""
    return _failed_url_tracker
