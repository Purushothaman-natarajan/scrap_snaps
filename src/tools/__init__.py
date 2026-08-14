"""Tools package - centralized tool registry and exports.

All tools are organized by domain:
- tools/web: Web search, page fetching, robots checking
- tools/media: Image download/analysis, video download/frame extraction
- tools/db: Database evidence persistence
- tools/utils: HTTP utilities, image hashing
"""

from src.tools.db import save_evidence
from src.tools.media import (
    analyze_image,
    deduplicate_images,
    download_image,
    download_video,
    extract_frames,
    score_video,
    select_best_frames,
)
from src.tools.web import (
    check_robots,
    extract_structured_data,
    fetch_page,
    fetch_page_js,
    search_images,
    search_videos,
    search_web,
)

__all__ = [
    # Web tools
    "search_web",
    "search_images",
    "search_videos",
    "fetch_page",
    "fetch_page_js",
    "extract_structured_data",
    "check_robots",
    # Media tools
    "download_image",
    "analyze_image",
    "deduplicate_images",
    "download_video",
    "extract_frames",
    "select_best_frames",
    "score_video",
    # DB tools
    "save_evidence",
]
