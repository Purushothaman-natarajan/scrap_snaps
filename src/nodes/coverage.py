from typing import Dict, Any
from src.state import ResearchState

def coverage(state: ResearchState) -> Dict[str, Any]:
    """
    Coverage Subgraph/Node (Gap Analyzer)
    Evaluates what's missing and decides if more research is needed.
    """
    print("--- COVERAGE NODE ---")
    
    required_views = state.get("required_views", ["front", "back", "left", "right", "top", "bottom", "detail"])
    discovered_views = state.get("discovered_views", {})
    
    missing_views = [v for v in required_views if v not in discovered_views]
    
    status = "complete" if not missing_views else "incomplete"
    
    return {
        "missing_views": missing_views,
        "status": status
    }

def route_after_coverage(state: ResearchState) -> str:
    """Routing function after coverage analysis."""
    if state.get("status") == "max_iterations_reached":
        return "complete"
    
    if state.get("status") == "incomplete":
        return "more_research"
    return "complete"
