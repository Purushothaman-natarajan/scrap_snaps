"""Discovery node - thin wrapper around ResearchAgent.discover."""

from src.agents.researcher import ResearchAgent
from src.state import ResearchState

_agent = ResearchAgent()


def discovery(state: ResearchState) -> dict:
    """Discovery Node (LLM-powered).

    Web search -> rank sources -> extract candidates -> canonicalize product identity.
    """
    return _agent.discover(state)
