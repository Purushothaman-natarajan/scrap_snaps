"""LangGraph state machine definition for the product research agent."""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.nodes.coverage import coverage, route_after_coverage
from src.nodes.discovery import discovery
from src.nodes.evidence import evidence
from src.nodes.media import media
from src.nodes.planner import planner
from src.nodes.verification import verification
from src.nodes.video_extract import video_extract
from src.state import ResearchState

logger = logging.getLogger(__name__)


def finalize(state: ResearchState) -> dict[str, Any]:
    """Finalize node to package up the results."""
    logger.info("Finalize node executing")
    return {"status": "done"}


def route_after_planner(state: ResearchState) -> str:
    """Routing function after planner.

    Routes to the correct execution node based on the first task type.
    Supported task types: discover, find_images, find_videos, verify_spec.
    """
    if state.get("status") == "max_iterations_reached":
        return "finalize"

    tasks = state.get("tasks", [])
    if not tasks:
        return "finalize"

    first_task = tasks[0].get("type")
    if first_task == "discover":
        return "discover"
    elif first_task == "verify_spec":
        return "evidence"
    elif first_task == "find_images":
        return "media"
    elif first_task == "find_videos":
        return "video_extract"

    return "finalize"


def build_graph() -> StateGraph:
    """Build and compile the research agent state graph.

    Graph topology:
        START -> planner -> {discover, evidence, media, video_extract}
        -> verify -> coverage -> {planner, finalize} -> END
    """
    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner)
    builder.add_node("discover", discovery)
    builder.add_node("evidence", evidence)
    builder.add_node("media", media)
    builder.add_node("video_extract", video_extract)
    builder.add_node("verify", verification)
    builder.add_node("coverage", coverage)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "planner")

    # Planner routes to the correct execution node based on the task type.
    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "discover": "discover",
            "evidence": "evidence",
            "media": "media",
            "video_extract": "video_extract",
            "finalize": "finalize",
        },
    )

    # All execution nodes feed into verification, regardless of task type.
    builder.add_edge("discover", "verify")
    builder.add_edge("evidence", "verify")
    builder.add_edge("media", "verify")
    builder.add_edge("video_extract", "verify")

    # After verification, coverage checks what's still missing.
    builder.add_edge("verify", "coverage")

    builder.add_conditional_edges(
        "coverage",
        route_after_coverage,
        {
            "more_research": "planner",
            "complete": "finalize",
        },
    )

    builder.add_edge("finalize", END)

    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()
