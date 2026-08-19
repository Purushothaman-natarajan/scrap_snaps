"""Graph builder for the research agent state machine using a plugin registry."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.config.logging import get_logger
from src.core.registry import register_default_components, registry
from src.state import ResearchState

logger = get_logger(__name__)


def finalize(state: ResearchState) -> dict[str, Any]:
    """Finalize node to package up the results."""
    logger.info("Finalize node executing")
    return {"status": "done"}


def route_after_planner(state: ResearchState) -> str:
    """Routing function after planner.

    Routes to the correct execution node based on the first task type.
    """
    status = state.get("status")
    if status in ("max_iterations_reached", "partial_complete"):
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


def build_graph(
    use_registry: bool = True,
    compile: bool = True,
) -> StateGraph | Any:
    """Build and optionally compile the research agent state graph.

    Args:
        use_registry: If True, register default components in the registry.
        compile: If True, compile the graph before returning.

    Returns:
        Compiled StateGraph if compile=True, otherwise the builder.

    Graph topology:
        START -> planner -> {discover, evidence, media, video_extract}
        -> verify -> coverage -> {planner, finalize} -> END

    Termination conditions:
        - All tasks complete (status == "complete")
        - Max iterations reached (status == "max_iterations_reached")
        - No new progress detected (status == "partial_complete")
        - Planner generates duplicate tasks (status == "partial_complete")
    """
    if use_registry:
        register_default_components()

    builder = StateGraph(ResearchState)

    # Add nodes - use registry if available, otherwise use direct imports
    if use_registry:
        planner_node = registry.get_node("planner")
        discovery_node = registry.get_node("discover")
        evidence_node = registry.get_node("evidence")
        media_node = registry.get_node("media")
        video_extract_node = registry.get_node("video_extract")
        verification_node = registry.get_node("verify")
        coverage_node = registry.get_node("coverage")
    else:
        from src.nodes.coverage import coverage as coverage_node
        from src.nodes.discovery import discovery as discovery_node
        from src.nodes.evidence import evidence as evidence_node
        from src.nodes.media import media as media_node
        from src.nodes.planner import planner as planner_node
        from src.nodes.verification import verification as verification_node
        from src.nodes.video_extract import video_extract as video_extract_node

    builder.add_node("planner", planner_node)
    builder.add_node("discover", discovery_node)
    builder.add_node("evidence", evidence_node)
    builder.add_node("media", media_node)
    builder.add_node("video_extract", video_extract_node)
    builder.add_node("verify", verification_node)
    builder.add_node("coverage", coverage_node)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "planner")

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

    builder.add_edge("discover", "verify")
    builder.add_edge("evidence", "verify")
    builder.add_edge("media", "verify")
    builder.add_edge("video_extract", "verify")

    builder.add_edge("verify", "coverage")

    from src.nodes.coverage import route_after_coverage
    builder.add_conditional_edges(
        "coverage",
        route_after_coverage,
        {
            "more_research": "planner",
            "complete": "finalize",
        },
    )

    builder.add_edge("finalize", END)

    if compile:
        compiled = builder.compile()
        if use_registry:
            registry.graph("research", compiled)
        return compiled

    return builder


if __name__ == "__main__":
    graph = build_graph()
    print("Graph built successfully")
    print("Registry summary:", registry.summary())
