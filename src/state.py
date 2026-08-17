"""TypedDict definitions for the LangGraph research agent state."""

from __future__ import annotations

from typing import TypedDict


class ResearchState(TypedDict):
    """TypedDict defining the full state schema for the research agent graph."""

    # User request
    query: str

    # Focus configuration
    focus_areas: list[str]
    focus_config: dict
    collect_specs: bool
    collect_media: str  # images, videos, or both

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

    # Cost / safety
    iterations: int
    max_iterations: int

    # Final
    confidence: float
    status: str
