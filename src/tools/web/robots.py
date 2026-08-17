"""Robots.txt checking tools."""

from langchain_core.tools import tool

from src.config.logging import get_logger
from src.tools.logging import log_tool_call
from src.tools.utils.http import can_fetch

logger = get_logger(__name__)


@tool
@log_tool_call
def check_robots(url: str) -> dict:
    """Check if a URL is allowed by robots.txt."""
    try:
        can = can_fetch(url)
        return {"url": url, "allowed": can}
    except Exception as e:
        logger.error("Error checking robots.txt for %s: %s", url, e)
        return {"url": url, "allowed": True, "error": str(e)}
