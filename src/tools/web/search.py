"""Web search tools using SerpAPI (Google Search)."""

from langchain_core.tools import tool
from serpapi import GoogleSearch

from src.config import MAX_IMAGE_RESULTS, SERPAPI_KEY
from src.config.logging import get_logger
from src.tools.logging import log_tool_call

logger = get_logger(__name__)


def _search_serpapi(params: dict) -> list[dict]:
    """Execute a SerpAPI search and return organic results."""
    params["api_key"] = SERPAPI_KEY
    search = GoogleSearch(params)
    return search.get_dict().get("organic_results", [])


@tool
@log_tool_call
def search_web(query: str, limit: int = 10) -> list[dict]:
    """Search the web for a given query using Google via SerpAPI."""
    try:
        params = {
            "q": query,
            "num": limit,
            "engine": "google",
        }
        results = _search_serpapi(params)
        return [
            {"url": r.get("link", ""), "title": r.get("title", ""), "snippet": r.get("snippet", "")}
            for r in results[:limit]
        ]
    except Exception as e:
        logger.error("SerpAPI search failed: %s", e)
        return []


@tool
@log_tool_call
def search_images(query: str, limit: int = MAX_IMAGE_RESULTS) -> list[dict]:
    """Search for images matching a query using Google Images via SerpAPI."""
    try:
        params = {
            "q": query,
            "num": limit,
            "engine": "google_images",
        }
        results = _search_serpapi(params)
        return [
            {"url": r.get("original", ""), "title": r.get("title", "")}
            for r in results[:limit]
            if r.get("original")
        ]
    except Exception as e:
        logger.error("Image search failed: %s", e)
        return []


@tool
@log_tool_call
def search_videos(query: str, limit: int = 10) -> list[dict]:
    """Search for YouTube videos matching a query using SerpAPI.

    Returns video metadata: url, title, duration, channel, view_count.
    The query should already include relevant modifiers (e.g., "review", "unboxing").
    """
    try:
        params = {
            "q": query,
            "engine": "youtube",
        }
        results = _search_serpapi(params)
        videos = []
        for r in results.get("video_results", [])[:limit]:
            videos.append({
                "url": r.get("link", ""),
                "title": r.get("title", ""),
                "snippet": r.get("description", ""),
                "channel": r.get("channel", ""),
                "duration": r.get("length", ""),
                "view_count": r.get("views", 0),
            })
        return videos[:limit]
    except Exception as e:
        logger.error("Video search failed: %s", e)
        return []
