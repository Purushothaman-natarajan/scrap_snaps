"""Web search tools using SerpAPI."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from serpapi import GoogleSearch

from src.config import settings
from src.config.logging import get_logger
from src.tools.logging import log_tool_call
from src.tools.web.cache import get_search_cache

logger = get_logger(__name__)


def _serpapi_search(params: dict[str, Any]) -> dict[str, Any]:
    """Execute a SerpAPI request and return the complete response dictionary.

    Results are cached per-run to avoid retrying the exact same query
    within a single graph execution.  Cache is cleared between runs.

    Enforces a per-row API call limit (SERPAPI_MAX_HITS_PER_ROW) to
    prevent burning through SerpAPI quota on repeated queries.

    Important:
        Different SerpAPI engines return different result fields:
        - google         -> organic_results
        - google_images  -> images_results
        - youtube        -> video_results
    """
    cache = get_search_cache()

    # Check cache first
    cached = cache.get(params)
    if cached is not None:
        return cached

    # Check per-row API call limit before making network call
    if not cache.can_call_api():
        logger.warning(
            "SerpAPI call skipped (per-row limit reached): engine=%s, query=%s",
            params.get("engine", ""),
            params.get("q") or params.get("search_query", ""),
        )
        return {"error": "SerpAPI per-row hit limit reached", "organic_results": []}

    api_key = settings.serpapi_key

    if not api_key:
        logger.error("SERPAPI_KEY is missing")
        return {
            "error": "SERPAPI_KEY is missing",
        }

    request_params = {
        **params,
        "api_key": api_key,
    }

    # Record the API call BEFORE making it (counts even if it fails)
    cache.record_api_call()

    try:
        response = GoogleSearch(request_params).get_dict()

    except Exception as exc:
        logger.error(
            "SerpAPI request failed: %s",
            exc,
            exc_info=True,
        )
        return {
            "error": str(exc),
        }

    if not isinstance(response, dict):
        logger.error(
            "Unexpected SerpAPI response type: %s",
            type(response).__name__,
        )
        return {
            "error": f"Unexpected response type: {type(response).__name__}",
        }

    if response.get("error"):
        logger.error(
            "SerpAPI returned an error: %s",
            response["error"],
        )

    # Only cache successful responses (no error key)
    if not response.get("error"):
        cache.put(params, response)

    return response


# ---------------------------------------------------------------------------
# Google Web Search
# ---------------------------------------------------------------------------


@tool
@log_tool_call
def search_web(query: str, limit: int = 10) -> list[dict]:
    """Search the web using Google via SerpAPI."""
    try:
        limit = max(1, min(limit, 100))

        response = _serpapi_search(
            {
                "engine": "google",
                "q": query,
                "num": limit,
            }
        )

        if response.get("error"):
            logger.error(
                "Google search failed: %s",
                response["error"],
            )
            return []

        organic_results = response.get("organic_results", [])

        if not isinstance(organic_results, list):
            logger.warning(
                "Unexpected organic_results type: %s",
                type(organic_results).__name__,
            )
            return []

        results: list[dict] = []

        for result in organic_results[:limit]:
            if not isinstance(result, dict):
                continue

            url = result.get("link", "")
            title = result.get("title", "")
            snippet = result.get("snippet", "")

            if not url:
                continue

            results.append(
                {
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                }
            )

        logger.info(
            "Found %d web results for query: %s",
            len(results),
            query,
        )

        return results

    except Exception as exc:
        logger.error(
            "Web search failed: %s",
            exc,
            exc_info=True,
        )
        return []


# ---------------------------------------------------------------------------
# Google Image Search
# ---------------------------------------------------------------------------


@tool
@log_tool_call
def search_images(
    query: str,
    limit: int | None = None,
) -> list[dict]:
    """Search for images using Google Images via SerpAPI."""
    try:
        if limit is None:
            limit = settings.max_image_results

        limit = max(1, min(limit, 100))

        response = _serpapi_search(
            {
                "engine": "google_images",
                "q": query,
                "num": limit,
            }
        )

        if response.get("error"):
            logger.error(
                "Google Images search failed: %s",
                response["error"],
            )
            return []

        image_results = response.get("images_results", [])

        if not isinstance(image_results, list):
            logger.warning(
                "Unexpected images_results type: %s",
                type(image_results).__name__,
            )
            return []

        images: list[dict] = []

        for result in image_results[:limit]:
            if not isinstance(result, dict):
                continue

            # SerpAPI normally exposes the full image URL as "original".
            original_url = result.get("original", "")

            # Thumbnail is only a fallback.
            thumbnail_url = result.get("thumbnail", "")

            image_url = original_url or thumbnail_url

            if not image_url:
                continue

            images.append(
                {
                    "url": image_url,
                    "title": result.get("title", ""),
                    "source": result.get("source", ""),
                    "thumbnail": thumbnail_url,
                    "original": original_url,
                    "link": result.get("link", ""),
                }
            )

        logger.info(
            "Found %d images for query: %s",
            len(images),
            query,
        )

        return images

    except Exception as exc:
        logger.error(
            "Image search failed: %s",
            exc,
            exc_info=True,
        )
        return []


# ---------------------------------------------------------------------------
# YouTube Search
# ---------------------------------------------------------------------------


@tool
@log_tool_call
def search_videos(
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Search for YouTube videos using SerpAPI.

    Returns video metadata including:
        url, title, snippet, channel, duration, view_count
    """
    try:
        limit = max(1, min(limit, 50))

        response = _serpapi_search(
            {
                "engine": "youtube",
                "search_query": query,
            }
        )

        if response.get("error"):
            logger.error(
                "YouTube search failed: %s",
                response["error"],
            )
            return []

        video_results = response.get("video_results", [])

        if not isinstance(video_results, list):
            logger.warning(
                "Unexpected video_results type: %s",
                type(video_results).__name__,
            )
            return []

        videos: list[dict] = []

        for result in video_results[:limit]:
            if not isinstance(result, dict):
                continue

            url = result.get("link", "")

            if not url:
                continue

            # SerpAPI's YouTube response can vary slightly depending
            # on the result. Keep the extraction defensive.
            channel = result.get("channel", "")

            if isinstance(channel, dict):
                channel = (
                    channel.get("name")
                    or channel.get("title")
                    or ""
                )

            views = result.get("views", 0)

            videos.append(
                {
                    "url": url,
                    "title": result.get("title", ""),
                    "snippet": (
                        result.get("description")
                        or result.get("snippet")
                        or ""
                    ),
                    "channel": channel,
                    "duration": result.get("length", ""),
                    "view_count": views,
                }
            )

        logger.info(
            "Found %d videos for query: %s",
            len(videos),
            query,
        )

        return videos

    except Exception as exc:
        logger.error(
            "Video search failed: %s",
            exc,
            exc_info=True,
        )
        return []
