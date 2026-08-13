from src.state import ResearchState


def test_research_state_has_required_fields():
    required_fields = [
        "query",
        "product",
        "candidates",
        "search_queries",
        "searched_queries",
        "sources",
        "evidence",
        "specifications",
        "images",
        "videos",
        "required_views",
        "discovered_views",
        "missing_views",
        "tasks",
        "completed_tasks",
        "failed_tasks",
        "iterations",
        "max_iterations",
        "confidence",
        "status",
    ]
    annotations = ResearchState.__annotations__
    for field in required_fields:
        assert field in annotations, f"Missing field: {field}"


def test_initial_state_structure():
    state: ResearchState = {
        "query": "test product",
        "product": {},
        "candidates": [],
        "search_queries": [],
        "searched_queries": [],
        "sources": [],
        "evidence": [],
        "specifications": {},
        "images": [],
        "videos": [],
        "required_views": ["front", "back", "side", "top"],
        "discovered_views": {},
        "missing_views": ["front", "back", "side", "top"],
        "tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "iterations": 0,
        "max_iterations": 10,
        "confidence": 0.0,
        "status": "started",
    }

    assert state["query"] == "test product"
    assert state["iterations"] == 0
    assert state["confidence"] == 0.0
    assert len(state["missing_views"]) == 4
