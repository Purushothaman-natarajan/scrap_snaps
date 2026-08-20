"""Search package - focus-aware query building and filtering."""

from src.search.filters import deduplicate_domains, filter_results, score_source
from src.search.focus import FocusArea, get_focus_config
from src.search.query_builder import SearchQuery, build_queries

__all__ = [
    "FocusArea",
    "get_focus_config",
    "build_queries",
    "SearchQuery",
    "filter_results",
    "score_source",
    "deduplicate_domains",
]
