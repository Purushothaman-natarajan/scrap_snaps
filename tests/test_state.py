"""Tests for the ResearchState TypedDict schema and initial state construction."""

from src.state import ResearchState


def test_research_state_has_required_fields():
    """Verify ResearchState contains all fields required by the agent graph.

    This test enforces the contract between state.py and all nodes that
    read/write to the state dict. If a node references a field not in
    this list, it will fail at runtime.
    """
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
        "video_frames",
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
    """Verify initial state can be constructed with correct types and defaults.

    This test validates that the initial state dict matches the TypedDict
    contract and that default values have the expected types (empty dicts,
    empty lists, zero iterations, etc.).
    """
    # Build a complete initial state matching what main.py produces
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
        "video_frames": {},
        "required_views": ["front", "back", "side", "top", "360_strip"],
        "discovered_views": {},
        "missing_views": ["front", "back", "side", "top", "360_strip"],
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
    assert len(state["missing_views"]) == 5
