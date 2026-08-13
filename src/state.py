from typing import TypedDict, Any, List, Dict

class ResearchState(TypedDict):
    # User request
    query: str

    # Canonical identity
    product: dict
    candidates: List[dict]

    # Discovery
    search_queries: List[str]
    searched_queries: List[str]
    sources: List[dict]

    # Evidence
    evidence: List[dict]
    specifications: dict

    # Media
    images: List[dict]
    videos: List[dict]

    # Image coverage
    required_views: List[str]
    discovered_views: Dict[str, List[str]]
    missing_views: List[str]

    # Autonomous control
    tasks: List[dict]
    completed_tasks: List[str]
    failed_tasks: List[dict]

    # Cost / safety
    iterations: int
    max_iterations: int

    # Final
    confidence: float
    status: str
