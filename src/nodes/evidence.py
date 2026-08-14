"""Evidence node - thin wrapper around ResearchAgent.extract_evidence."""

from src.agents.researcher import ResearchAgent
from src.state import ResearchState

_agent = ResearchAgent()


def evidence(state: ResearchState) -> dict:
    """Evidence Node (LLM-powered).

    Search -> Fetch Page -> Extract Claims.
    """
    return _agent.extract_evidence(state)
