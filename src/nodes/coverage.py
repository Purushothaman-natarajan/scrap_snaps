"""Coverage analysis node - thin wrapper around CoverageAgent."""

from src.agents.coverage import CoverageAgent
from src.state import ResearchState

_agent = CoverageAgent()


def coverage(state: ResearchState) -> dict:
    """Coverage Node (Gap Analyzer).

    Evaluates what's missing from both image search and video extraction.
    Checks discovered_views (from all sources) against required_views.
    """
    return _agent.analyze(state)


def route_after_coverage(state: ResearchState) -> str:
    """Routing function after coverage analysis."""
    return _agent.route(state)
