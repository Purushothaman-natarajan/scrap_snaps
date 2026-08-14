"""Verification node - thin wrapper around VerifierAgent."""

from src.agents.verifier import VerifierAgent
from src.state import ResearchState

_agent = VerifierAgent()


def verification(state: ResearchState) -> dict:
    """Verification Node.

    Resolves conflicts, evaluates evidence quality based on source priority.
    """
    return _agent.run(state)
