"""Tools compatibility layer - imports from new tool modules.

This module maintains backward compatibility for existing imports while
using the new modular tool structure internally.
"""

from src.tools.db.evidence import save_evidence
from src.tools.media.images import analyze_image, deduplicate_images, download_image
from src.tools.media.video import download_video, extract_frames, score_video, select_best_frames
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
    "download_image",
    "analyze_image",
    "deduplicate_images",
    "download_video",
    "extract_frames",
    "select_best_frames",
    "score_video",
    "save_evidence",
]
