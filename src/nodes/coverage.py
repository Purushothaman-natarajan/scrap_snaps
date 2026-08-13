"""Coverage analysis node - evaluate what's missing and decide if more research is needed."""

from __future__ import annotations

import logging

from src.state import ResearchState

logger = logging.getLogger(__name__)


def coverage(state: ResearchState) -> dict:
    """Coverage Node (Gap Analyzer).

    Evaluates what's missing from both image search and video extraction.
    Checks discovered_views (from all sources) against required_views.
    """
    logger.info("Coverage node executing")

    required_views = state.get("required_views", [])
    discovered_views = state.get("discovered_views", {})

    # Views not yet discovered are considered missing.
    # discovered_views is populated by both media.py and video_extract.py.
    missing_views = [v for v in required_views if v not in discovered_views]

    status = "complete" if not missing_views else "incomplete"

    images_count = len(state.get("images", []))
    videos_count = len(state.get("videos", []))
    logger.info(
        "Coverage: %d/%d views found, %d images, %d videos",
        len(required_views) - len(missing_views),
        len(required_views),
        images_count,
        videos_count,
    )

    return {"missing_views": missing_views, "status": status}


def route_after_coverage(state: ResearchState) -> str:
    """Routing function after coverage analysis."""
    if state.get("status") == "max_iterations_reached":
        return "complete"

    if state.get("status") == "incomplete":
        return "more_research"
    return "complete"
