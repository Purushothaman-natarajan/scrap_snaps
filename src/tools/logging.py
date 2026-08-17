"""Tool I/O logging decorator for debugging and auditing."""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

from src.config.logging import get_logger

logger = get_logger(__name__)


def log_tool_call(func: Callable) -> Callable:
    """Decorator that logs tool input, output, and errors.

    Logs at DEBUG level for normal calls, ERROR level for failures.
    All output goes to the file handler when LOG_CAPTURE=true.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        tool_name = func.__name__
        start = time.monotonic()

        # Log input (truncate large args for readability)
        safe_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, str) and len(v) > 200:
                safe_kwargs[k] = v[:200] + f"...[{len(v)} chars]"
            else:
                safe_kwargs[k] = v

        logger.debug("tool_input", tool=tool_name, args=str(args)[:200], kwargs=safe_kwargs)

        try:
            result = func(*args, **kwargs)
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)

            # Log output summary (don't dump full result)
            if isinstance(result, list):
                summary = f"list[{len(result)}]"
            elif isinstance(result, dict):
                summary = f"dict[{len(result)} keys]"
            elif isinstance(result, str):
                summary = f"str[{len(result)} chars]"
            else:
                summary = type(result).__name__

            logger.debug(
                "tool_output",
                tool=tool_name,
                result=summary,
                elapsed_ms=elapsed_ms,
            )
            return result

        except Exception as e:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            logger.error(
                "tool_failure",
                tool=tool_name,
                error=str(e),
                error_type=type(e).__name__,
                elapsed_ms=elapsed_ms,
                exc_info=True,
            )
            raise

    return wrapper
