"""Search package - focus-aware query building and filtering."""

from src.search.focus import FocusArea, get_focus_config
from src.search.query_builder import build_queries, SearchQuery
from src.search.filters import filter_results, score_source, deduplicate_domains

__all__ = [
    "FocusArea",
    "get_focus_config",
    "build_queries",
    "SearchQuery",
    "filter_results",
    "score_source",
    "deduplicate_domains",
]
