from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src.llm import get_llm
from src.state import ResearchState

logger = logging.getLogger(__name__)


class Task(BaseModel):
    """A research task to be executed by the agent."""

    type: str = Field(description="The type of task: 'discover', 'find_images', 'verify_spec'")
    target: str = Field(
        description="The target of the task (e.g. 'front view', 'weight', or the product query)"
    )
    priority: float = Field(description="Priority from 0.0 to 1.0")


class PlannerOutput(BaseModel):
    """Structured output from the planner LLM call."""

    tasks: list[Task] = Field(description="The list of next tasks to execute")


def planner(state: ResearchState) -> dict:
    """Planner Node (LLM-powered).

    Evaluates current state, generates tasks using LLM, and decides next actions.
    """
    logger.info("Planner node executing")

    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 30)

    iterations += 1

    if iterations > max_iterations:
        return {"status": "max_iterations_reached", "tasks": [], "iterations": iterations}

    tasks = state.get("tasks", [])
    if tasks:
        return {"tasks": tasks, "iterations": iterations}

    llm = get_llm().with_structured_output(PlannerOutput)

    prompt = f"""
    You are the Planner for an autonomous Product Research Agent.
    Your goal is to gather comprehensive information and images about a product.

    Current State:
    - Query: {state.get("query")}
    - Product Identified: {bool(state.get("product"))}
    - Specifications Found: {list(state.get("specifications", {}).keys())}
    - Missing Views: {state.get("missing_views", [])}
    - Failed Tasks: {len(state.get("failed_tasks", []))}

    Decide what tasks to execute next.
    If the product is not identified, output a 'discover' task.
    If the product is identified but missing views, output 'find_images' tasks for those views.
    If the product is identified but lacks specs (weight, dimensions, battery),
    output 'verify_spec'.
    """

    try:
        result = llm.invoke(prompt)
        new_tasks = [t.model_dump() for t in result.tasks]
        logger.info("Planner generated %d tasks", len(new_tasks))
        return {"tasks": new_tasks, "iterations": iterations}
    except Exception as e:
        logger.warning("Planner LLM failed: %s", e)
        if not state.get("product"):
            return {
                "tasks": [{"type": "discover", "target": state.get("query", ""), "priority": 1.0}],
                "iterations": iterations,
            }
        elif state.get("missing_views"):
            return {
                "tasks": [
                    {
                        "type": "find_images",
                        "target": state.get("missing_views")[0],
                        "priority": 0.9,
                    }
                ],
                "iterations": iterations,
            }
        else:
            return {
                "tasks": [{"type": "verify_spec", "target": "general", "priority": 0.8}],
                "iterations": iterations,
            }
