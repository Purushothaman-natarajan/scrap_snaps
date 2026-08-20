"""In-memory search cache with per-run SerpAPI hit limiting.

Provides SearchCache singleton for caching SerpAPI results within a single
graph execution. Cache is cleared between runs (or manually via ``clear()``).

Features:
- Query normalization (lowercase, strip, sorted words) for fuzzy key matching
- Per-run API call limit (SERPAPI_MAX_HITS_PER_ROW, default 20) prevents
  burning through SerpAPI quota on repeated queries. Counter is reset when
  cache is cleared (between rows in pipeline mode, between runs in single mode).
- Cache eviction when max size reached (SEARCH_CACHE_SIZE, default 500)
- Stats tracking: hits, misses, api_calls, limit_reached
"""

from __future__ import annotations

import re
from typing import Any

from src.config import SEARCH_CACHE_SIZE, SERPAPI_MAX_HITS_PER_ROW
from src.config.logging import get_logger

logger = get_logger(__name__)


def _normalize_query(q: str) -> str:
    """Normalize a search query for cache key matching.

    - Lowercase
    - Strip whitespace
    - Collapse multiple spaces
    - Sort words alphabetically (so "iPhone 15 case" == "case 15 iPhone")
    """
    q = q.lower().strip()
    q = re.sub(r"\s+", " ", q)
    words = q.split()
    words.sort()
    return " ".join(words)


class SearchCache:
    """Per-run cache for SerpAPI search results with hit limiting.

    - Avoids retrying the same query+engine+limit combinations
      within a single graph execution.
    - Normalizes queries (lowercase, sorted words) for fuzzy key matching.
    - Tracks actual API calls (cache misses) and enforces a per-run limit
      to prevent burning through SerpAPI quota. Counter resets on clear().
    - Cache is cleared between runs (or manually via ``clear()``).
    """

    def __init__(self, max_size: int = SEARCH_CACHE_SIZE) -> None:
        self._cache: dict[tuple, dict[str, Any]] = {}
        self._max_size = max_size
        self._hits = 0        # cache hits (returned from cache)
        self._misses = 0      # cache misses (went to network)
        self._api_calls = 0   # actual SerpAPI calls made
        self._max_per_row = SERPAPI_MAX_HITS_PER_ROW
        self._row_limit_reached = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, params: dict[str, Any]) -> dict[str, Any] | None:
        """Return cached response for the given params, or ``None``."""
        key = self._make_key(params)
        entry = self._cache.get(key)
        if entry is not None:
            self._hits += 1
            logger.debug(
                "Search cache HIT for %s (total hits: %d)",
                key,
                self._hits,
            )
            return entry
        self._misses += 1
        logger.debug(
            "Search cache MISS for %s (total misses: %d)",
            key,
            self._misses,
        )
        return None

    def can_call_api(self) -> bool:
        """Check if we're still within the per-row API call limit."""
        if self._row_limit_reached:
            return False
        if self._api_calls >= self._max_per_row:
            self._row_limit_reached = True
            logger.warning(
                "SerpAPI hit limit reached (%d/%d). "
                "Further searches in this row will return empty results.",
                self._api_calls,
                self._max_per_row,
            )
            return False
        return True

    def record_api_call(self) -> None:
        """Record that a SerpAPI call was made (cache miss -> network)."""
        self._api_calls += 1

    def remaining(self) -> int:
        """Return remaining SerpAPI calls allowed in this row."""
        return max(0, self._max_per_row - self._api_calls)

    def put(self, params: dict[str, Any], response: dict[str, Any]) -> None:
        """Store a response in the cache."""
        key = self._make_key(params)

        if len(self._cache) >= self._max_size and key not in self._cache:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = response

    def clear(self) -> None:
        """Clear the cache and reset all counters."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._api_calls = 0
        self._row_limit_reached = False
        logger.debug("Search cache cleared")

    @property
    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "api_calls": self._api_calls,
            "max_per_row": self._max_per_row,
            "limit_reached": self._row_limit_reached,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(params: dict[str, Any]) -> tuple:
        """Build a normalized, hashable cache key from SerpAPI params.

        Only includes the fields that affect the result: engine, q/search_query, num.
        Query is normalized (lowercase, sorted words) for fuzzy matching.
        API key is excluded from the key.
        """
        raw_q = params.get("q") or params.get("search_query", "")
        normalized_q = _normalize_query(raw_q) if isinstance(raw_q, str) else raw_q
        return (
            params.get("engine", ""),
            normalized_q,
            params.get("num", 0),
        )


# Module-level singleton — one cache per process, cleared between runs.
_search_cache = SearchCache()


def get_search_cache() -> SearchCache:
    """Return the module-level search cache singleton."""
    return _search_cache
