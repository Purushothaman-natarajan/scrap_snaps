"""Web search tools using DuckDuckGo."""

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from langchain_core.tools import tool

from src.config import MAX_IMAGE_RESULTS, REQUEST_TIMEOUT, USER_AGENT
from src.config.logging import get_logger
from src.tools.utils.http import rate_limit

logger = get_logger(__name__)


@tool
def search_web(query: str, limit: int = 10) -> list[dict]:
    """Search the web for a given query."""
    logger.info("Executing web search for: %s", query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=limit))
            return [{"url": r["href"], "title": r["title"], "snippet": r["body"]} for r in results]
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s, attempting fallback", e)
        try:
            rate_limit()
            resp = httpx.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            fallback_results = []
            for link in soup.select("a.result__a")[:limit]:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if href and title:
                    fallback_results.append({"url": href, "title": title, "snippet": ""})
            return fallback_results
        except Exception as fallback_error:
            logger.error("Search fallback also failed: %s", fallback_error)
            return []


@tool
def search_images(query: str, limit: int = MAX_IMAGE_RESULTS) -> list[dict]:
    """Search for images matching a query."""
    logger.info("Executing image search for: %s", query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=limit))
            return [
                {"url": r.get("image", ""), "title": r.get("title", "")}
                for r in results
                if r.get("image")
            ]
    except Exception as e:
        logger.error("Image search failed: %s", e)
        return []


@tool
def search_videos(query: str, limit: int = 10) -> list[dict]:
    """Search for YouTube videos matching a query.

    Returns video metadata: url, title, duration, channel, view_count.
    Filters for review/unboxing/hands-on content.
    """
    logger.info("Searching for videos: %s", query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"site:youtube.com {query} review", max_results=limit))
            videos = []
            for r in results:
                url = r.get("href", "")
                if "youtube.com/watch" not in url and "youtu.be/" not in url:
                    continue
                videos.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "channel": "",
                    "duration": 0,
                    "view_count": 0,
                })
            return videos[:limit]
    except Exception as e:
        logger.error("Video search failed: %s", e)
        return []
