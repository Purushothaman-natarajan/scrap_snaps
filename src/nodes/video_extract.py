"""Video extraction node - thin wrapper around MediaAgent.collect_videos."""

from src.agents.media_collector import MediaAgent
from src.state import ResearchState

_agent = MediaAgent()


def video_extract(state: ResearchState) -> dict:
    """Video extraction node.

    Searches YouTube for product videos, downloads the best ones,
    extracts key frames via scene detection, and classifies views.
    """
    return _agent.collect_videos(state)
