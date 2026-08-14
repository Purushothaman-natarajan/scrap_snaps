"""Planner node - thin wrapper around PlannerAgent."""

from src.agents.planner import PlannerAgent
from src.state import ResearchState

_agent = PlannerAgent()


def planner(state: ResearchState) -> dict:
    """Planner Node (LLM-powered).

    Evaluates current state, generates tasks using LLM, and decides next actions.
    """
    return _agent.run(state)
