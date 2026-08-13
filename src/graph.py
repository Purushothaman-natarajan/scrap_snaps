from langgraph.graph import StateGraph, START, END
from src.state import ResearchState
from src.nodes.planner import planner
from src.nodes.discovery import discovery
from src.nodes.evidence import evidence
from src.nodes.media import media
from src.nodes.verification import verification
from src.nodes.coverage import coverage, route_after_coverage

def finalize(state: ResearchState):
    """Finalize node to package up the results."""
    print("--- FINALIZE NODE ---")
    return {"status": "done"}

def route_after_planner(state: ResearchState) -> str:
    """Routing function after planner."""
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
        
    return "finalize"

def build_graph():
    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner)
    builder.add_node("discover", discovery)
    builder.add_node("evidence", evidence)
    builder.add_node("media", media)
    builder.add_node("verify", verification)
    builder.add_node("coverage", coverage)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "planner")
    
    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "discover": "discover",
            "evidence": "evidence",
            "media": "media",
            "finalize": "finalize"
        }
    )

    # After discovery, go to evidence or media based on what planner wanted, 
    # but for simplicity, we just flow into verification and then planner again.
    # In a full system, you could route this directly.
    builder.add_edge("discover", "verify")
    builder.add_edge("evidence", "verify")
    builder.add_edge("media", "verify")
    
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
    # graph.get_graph().draw_png("graph.png")
