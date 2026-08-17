"""Search query builder - generates optimized queries from focus areas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.search.focus import FocusArea, FocusConfig


class SearchQuery(BaseModel):
    """A single search query with metadata."""

    query: str
    focus_area: FocusArea | None = None
    engine: str = "google"  # google, google_images, youtube
    priority: float = 0.5
    description: str = ""


# Map focus areas to search engines
FOCUS_ENGINES: dict[FocusArea, str] = {
    FocusArea.PRODUCT_PAGES: "google",
    FocusArea.SELLER_IMAGES: "google_images",
    FocusArea.YOUTUBE: "youtube",
    FocusArea.PRICE_COMPARISON: "google",
    FocusArea.SPECS: "google",
}

# Map task types to which focus areas are relevant
TASK_FOCUS_MAP: dict[str, list[FocusArea]] = {
    "discover": [FocusArea.SPECS, FocusArea.PRODUCT_PAGES],
    "verify_spec": [FocusArea.SPECS, FocusArea.PRODUCT_PAGES],
    "find_images": [FocusArea.SELLER_IMAGES, FocusArea.PRODUCT_PAGES],
    "find_videos": [FocusArea.YOUTUBE],
}


def _build_site_query(base_query: str, domain: str) -> str:
    """Build a site-scoped search query."""
    return f'site:{domain} "{base_query}"'


def _build_modifier_query(base_query: str, modifier: str) -> str:
    """Build a query with a focus modifier."""
    return f"{base_query} {modifier}"


def build_queries(
    base_query: str,
    focus: FocusConfig | None = None,
    task_type: str | None = None,
    limit: int = 5,
) -> list[SearchQuery]:
    """Build optimized search queries based on focus areas.

    Args:
        base_query: The product query (e.g., "Sony WH-1000XM5").
        focus: Focus configuration with active areas.
        task_type: Current task type to determine relevant focus areas.
        limit: Maximum number of queries to return.

    Returns:
        List of SearchQuery objects, sorted by priority.
    """
    queries: list[SearchQuery] = []

    if not focus or not focus.areas:
        # No focus - generate a single generic query
        queries.append(
            SearchQuery(
                query=base_query,
                engine="google",
                priority=0.5,
                description="generic search",
            )
        )
        return queries[:limit]

    # Determine which focus areas are relevant for this task
    relevant_areas = focus.areas
    if task_type and task_type in TASK_FOCUS_MAP:
        task_focus = TASK_FOCUS_MAP[task_type]
        # Use task-specific focus areas if they overlap with configured areas
        relevant_overlap = [a for a in task_focus if a in focus.areas]
        if relevant_overlap:
            relevant_areas = relevant_overlap

    for area in relevant_areas:
        modifiers = focus.get_modifiers(area)
        engine = FOCUS_ENGINES.get(area, "google")

        # Build queries with modifiers
        for i, modifier in enumerate(modifiers[:2]):  # max 2 modifiers per area
            query = _build_modifier_query(base_query, modifier)
            priority = 0.9 - (i * 0.1)  # first modifier higher priority

            queries.append(
                SearchQuery(
                    query=query,
                    focus_area=area,
                    engine=engine,
                    priority=priority,
                    description=f"{area.value}: {modifier}",
                )
            )

        # For product pages and specs, also add site-scoped queries
        if area in (FocusArea.PRODUCT_PAGES, FocusArea.SPECS, FocusArea.YOUTUBE):
            domains = FOCUS_DOMAINS.get(area, [])[:2]  # top 2 domains
            for domain in domains:
                query = _build_site_query(base_query, domain)
                queries.append(
                    SearchQuery(
                        query=query,
                        focus_area=area,
                        engine="google",
                        priority=0.7,
                        description=f"site:{domain}",
                    )
                )

    # Sort by priority descending
    queries.sort(key=lambda q: q.priority, reverse=True)

    return queries[:limit]


# Re-export for convenience
from src.search.focus import FOCUS_DOMAINS  # noqa: E402
