"""TypedDict definitions for the LangGraph research agent state.

Defines ResearchState — the single TypedDict that flows through the entire
graph. All nodes read from and write to this state.

Also provides ``create_initial_state()`` which standardizes initial state
construction across single-query and batch pipeline modes.
"""

from __future__ import annotations

from typing import TypedDict


class ResearchState(TypedDict, total=False):
    """TypedDict defining the full state schema for the research agent graph."""

    # User request
    query: str
    __row_index: int  # Excel row number (0 for single-query)

    # Focus configuration
    focus_areas: list[str]
    focus_config: dict
    collect_specs: bool
    collect_media: str | None  # 7 modes: images, videos, video_urls, video_frames,
    # images_and_video_urls, both, none (None == none)

    # Canonical identity
    product: dict
    candidates: list[dict]

    # Discovery
    search_queries: list[str]
    searched_queries: list[str]
    sources: list[dict]

    # Evidence
    evidence: list[dict]
    specifications: dict

    # Media
    images: list[dict]
    videos: list[dict]
    video_frames: dict[str, list[str]]

    # Image coverage
    required_views: list[str]
    discovered_views: dict[str, list[str]]
    missing_views: list[str]

    # Autonomous control
    tasks: list[dict]
    completed_tasks: list[str]
    failed_tasks: list[dict]

    # Failure tracking - prevents infinite retry loops
    failed_media_urls: list[str]
    previous_task_fingerprints: list[str]

    # Coverage cycle counter - forces termination after N cycles
    _coverage_cycles: int
    _prev_images_count: int
    _prev_specs_count: int
    _prev_views_count: int

    # Cost / safety
    iterations: int
    max_iterations: int
    serpapi_budget_remaining: int

    # Final
    confidence: float
    status: str
    error: str


def create_initial_state(
    query: str,
    focus_areas: list[str],
    focus_config: dict,
    collect_specs: bool,
    collect_media: str | None,
    max_iterations: int,
    **kwargs
) -> ResearchState:
    """Create a standardized initial state for the research graph."""
    from src.config import REQUIRED_VIEWS, SERPAPI_MAX_HITS_PER_ROW

    state: ResearchState = {
        "query": query,
        "focus_areas": focus_areas,
        "focus_config": focus_config,
        "collect_specs": collect_specs,
        "collect_media": collect_media,
        "product": {},
        "candidates": [],
        "search_queries": [],
        "searched_queries": [],
        "sources": [],
        "evidence": [],
        "specifications": {},
        "images": [],
        "videos": [],
        "video_frames": {},
        "required_views": REQUIRED_VIEWS.copy(),
        "discovered_views": {},
        "missing_views": REQUIRED_VIEWS.copy(),
        "tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "failed_media_urls": [],
        "previous_task_fingerprints": [],
        "_coverage_cycles": 0,
        "_prev_images_count": 0,
        "_prev_specs_count": 0,
        "_prev_views_count": 0,
        "iterations": 0,
        "max_iterations": max_iterations,
        "serpapi_budget_remaining": SERPAPI_MAX_HITS_PER_ROW,
        "confidence": 0.0,
        "status": "started",
        "__row_index": 0,
        "error": "",
    }

    # Merge any additional kwargs (like __row_index)
    state.update(kwargs) # type: ignore

    return state
