"""Web tools package - search, fetch, and robots checking."""

from src.tools.web.fetch import extract_structured_data, fetch_page, fetch_page_js
from src.tools.web.robots import check_robots
from src.tools.web.search import search_images, search_videos, search_web

__all__ = [
    "search_web",
    "search_images",
    "search_videos",
    "fetch_page",
    "fetch_page_js",
    "extract_structured_data",
    "check_robots",
]
