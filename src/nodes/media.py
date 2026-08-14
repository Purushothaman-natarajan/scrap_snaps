"""Media acquisition node - thin wrapper around MediaAgent.collect_images."""

from src.agents.media_collector import MediaAgent
from src.state import ResearchState

_agent = MediaAgent()


def media(state: ResearchState) -> dict:
    """Media Node.

    Image searches -> download candidates -> deduplicate -> classify views.
    """
    return _agent.collect_images(state)
