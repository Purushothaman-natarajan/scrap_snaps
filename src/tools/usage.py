"""Usage tracker - accumulates token counts and API call stats per run."""

from __future__ import annotations

import threading
import time
from typing import Any


class UsageTracker:
    """Thread-safe accumulator for LLM token usage and API call stats.

    Tracks input/output tokens from LLM calls and provides a unified
    stats dict for persistence to DB and JSON.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._input_tokens = 0
        self._output_tokens = 0
        self._total_tokens = 0
        self._llm_calls = 0
        self._start_time: float | None = None

    def start(self) -> None:
        """Start the timer for elapsed_seconds."""
        self._start_time = time.monotonic()

    def record_llm(self, response: Any) -> None:
        """Extract token usage from an AIMessage response and accumulate.

        Args:
            response: The AIMessage returned by llm.invoke().
        """
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            meta = getattr(response, "response_metadata", {})
            usage = meta.get("token_usage")

        if usage is None:
            self._llm_calls += 1
            return

        with self._lock:
            self._llm_calls += 1
            if isinstance(usage, dict):
                self._input_tokens += usage.get("prompt_tokens", 0) or usage.get(
                    "input_tokens", 0
                )
                self._output_tokens += usage.get("completion_tokens", 0) or usage.get(
                    "output_tokens", 0
                )
                self._total_tokens += usage.get("total_tokens", 0)
            else:
                self._input_tokens += getattr(usage, "input_tokens", 0)
                self._output_tokens += getattr(usage, "output_tokens", 0)
                self._total_tokens += getattr(usage, "total_tokens", 0)

    def get_stats(self, search_cache_stats: dict | None = None) -> dict:
        """Return accumulated stats as a dict.

        Args:
            search_cache_stats: Optional dict from SearchCache.stats to merge in.
        """
        elapsed = 0.0
        if self._start_time is not None:
            elapsed = round(time.monotonic() - self._start_time, 1)

        stats: dict[str, Any] = {
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "total_tokens": self._total_tokens,
            "llm_calls": self._llm_calls,
            "elapsed_seconds": elapsed,
        }

        if search_cache_stats:
            stats["serpapi_calls"] = search_cache_stats.get("api_calls", 0)
            stats["serpapi_hits"] = search_cache_stats.get("hits", 0)
            stats["serpapi_misses"] = search_cache_stats.get("misses", 0)

        return stats

    def reset(self) -> None:
        """Reset all counters for the next row/run."""
        with self._lock:
            self._input_tokens = 0
            self._output_tokens = 0
            self._total_tokens = 0
            self._llm_calls = 0
            self._start_time = time.monotonic()


_tracker = UsageTracker()


def get_usage_tracker() -> UsageTracker:
    """Get the global usage tracker singleton."""
    return _tracker
