"""Tool I/O logging decorators for debugging and auditing."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from src.config.logging import get_logger

logger = get_logger(__name__)

# Tools that should log payload at INFO (not just DEBUG) for default visibility
_INFO_TOOLS = {"search_web", "search_images", "search_videos", "download_image", "download_video"}


def _truncate(value: Any, limit: int = 300) -> Any:
    """Truncate long strings/lists for logging."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"...[{len(value)} chars]"
    if isinstance(value, list) and len(value) > 5:
        preview = value[:3]
        return f"list[{len(value)}] {str(preview)[:limit]}..."
    if isinstance(value, dict) and len(str(value)) > limit:
        return str(value)[:limit] + "..."
    return value


def log_tool_call(func: Callable) -> Callable:
    """Decorator that logs tool input, output, and errors.

    Critical tools (search_*, download_*) log at INFO with payload;
    others at DEBUG. All go to file when LOG_CAPTURE=true.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        tool_name = func.__name__
        start = time.monotonic()
        is_info = tool_name in _INFO_TOOLS

        # Build truncated payload for logging
        safe_kwargs = {k: _truncate(v) for k, v in kwargs.items()}
        log_fn = logger.info if is_info else logger.debug
        log_fn("tool_input", tool=tool_name, args=_truncate(str(args)[:300]), kwargs=safe_kwargs)

        try:
            result = func(*args, **kwargs)
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)

            # Build summary + truncated payload for INFO tools
            if isinstance(result, list):
                summary = f"list[{len(result)}]"
                payload = _truncate([str(x)[:120] for x in result[:3]])
            elif isinstance(result, dict):
                summary = f"dict[{len(result)} keys]"
                payload = _truncate(result)
            elif isinstance(result, str):
                summary = f"str[{len(result)} chars]"
                payload = _truncate(result)
            else:
                summary = type(result).__name__
                payload = summary

            if is_info:
                logger.info("tool_output", tool=tool_name, result=summary, payload=payload, elapsed_ms=elapsed_ms)
            else:
                logger.debug("tool_output", tool=tool_name, result=summary, elapsed_ms=elapsed_ms)
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


def log_state(node_name: str | None = None) -> Callable:
    """Decorator for agent/node methods to log ResearchState in/out.

    Logs at INFO: query, tasks, images/specs/views counts, missing_views, budget.
    At DEBUG (when LOG_VERBOSE=true): full tasks, product, candidates, claims.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find state dict (first dict arg with known keys)
            state = None
            for a in list(args) + list(kwargs.values()):
                if isinstance(a, dict) and ("query" in a or "status" in a or "iterations" in a):
                    state = a
                    break
            name = node_name or func.__name__
            if state is not None:
                try:
                    from src.config.settings import get_settings  # late import to avoid cycle

                    verbose = False
                    try:
                        verbose = bool(get_settings().log_verbose)  # type: ignore
                    except Exception:
                        pass
                    in_stats = {
                        "query": _truncate(state.get("query", ""), 80),
                        "tasks": state.get("tasks", []) if verbose else [t.get("type") for t in state.get("tasks", [])],
                        "images": len(state.get("images", [])),
                        "specs": len(state.get("specifications", {})),
                        "views": f"{len(state.get('discovered_views', {}))}/{len(state.get('required_views', []))}",
                        "missing": state.get("missing_views", [])[:4] if not verbose else state.get("missing_views", []),
                        "budget": state.get("serpapi_budget_remaining", "?"),
                        "iter": state.get("iterations", "?"),
                    }
                    if verbose:
                        in_stats["product"] = _truncate(str(state.get("product", {})), 200)
                    logger.info(f"-> {name} in", **in_stats)
                except Exception:
                    logger.info("→ %s in", name)

            t0 = time.monotonic()
            result = func(*args, **kwargs)
            dt = round((time.monotonic() - t0) * 1000, 1)

            if isinstance(result, dict):
                out_stats: dict[str, Any] = {}
                for k, v in result.items():
                    if isinstance(v, list):
                        if k == "tasks":
                            out_stats[k] = [t.get("type") + ":" + t.get("target", "")[:30] for t in v[:5]]
                            if len(v) > 5:
                                out_stats[k].append(f"... +{len(v)-5}")
                        elif k in ("images", "videos", "sources", "evidence"):
                            out_stats[k] = f"+{len(v)}" if state is not None and k in state else f"list[{len(v)}]"
                        else:
                            out_stats[k] = f"list[{len(v)}]"
                    elif isinstance(v, dict):
                        out_stats[k] = f"dict[{len(v)} keys]" if len(v) > 3 else str(_truncate(v, 150))
                    else:
                        out_stats[k] = _truncate(v, 120)
                logger.info(f"<- {name} out in {dt:.0f}ms", **out_stats)
                # DEBUG full payload when verbose
                try:
                    from src.config.settings import get_settings

                    if bool(get_settings().log_verbose):  # type: ignore
                        logger.debug("state_delta", node=name, delta=json.dumps(out_stats, default=str)[:2000])
                except Exception:
                    pass
            else:
                logger.info(f"<- {name} out in {dt:.0f}ms", result=_truncate(str(result), 300))
            return result

        return wrapper

    return decorator
