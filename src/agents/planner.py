"""Planner agent - LLM-powered task generation and iteration budget control."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.search.focus import FocusArea, FocusConfig


class Task(BaseModel):
    """A research task to be executed by the agent."""

    type: str = Field(
        description="Task type: 'discover', 'find_images', 'find_videos', 'verify_spec'"
    )
    target: str = Field(
        description="The target of the task (e.g. 'front view', 'weight', or the product query)"
    )
    priority: float = Field(description="Priority from 0.0 to 1.0")


class PlannerOutput(BaseModel):
    """Structured output from the planner LLM call."""

    tasks: list[Task] = Field(description="The list of next tasks to execute")


class PlannerAgent(BaseAgent):
    """Planner Agent - generates research tasks using LLM."""

    name = "planner"

    def _get_focus(self, state: dict) -> FocusConfig:
        """Extract FocusConfig from state."""
        return FocusConfig.from_dict(state.get("focus_config", {}))

    def _can_collect_specs(self, state: dict) -> bool:
        """Check if we should collect specs."""
        return state.get("collect_specs", True)

    def _can_collect_media(self, state: dict) -> str:
        """Check what media we should collect: images, videos, or both."""
        return state.get("collect_media", "both")

    def run(self, state: dict) -> dict:
        """Execute the planner logic."""
        self.logger.info("Planner agent executing")

        iterations = state.get("iterations", 0)
        max_iterations = state.get("max_iterations", 30)
        iterations += 1

        if iterations > max_iterations:
            return {"status": "max_iterations_reached", "tasks": [], "iterations": iterations}

        tasks = state.get("tasks", [])
        if tasks:
            return {"tasks": tasks, "iterations": iterations}

        llm = self.get_llm().with_structured_output(PlannerOutput)
        focus = self._get_focus(state)
        collect_specs = self._can_collect_specs(state)
        collect_media = self._can_collect_media(state)

        # Build focus-aware context for the planner
        focus_context = ""
        if focus.areas:
            area_names = [a.value for a in focus.areas]
            focus_context = f"\n- Focus Areas: {', '.join(area_names)}"

        # Build collect context
        collect_context = f"\n- Collect Specs: {collect_specs}"
        collect_context += f"\n- Collect Media: {collect_media}"
        if not collect_specs:
            collect_context += "\n  (Skip spec extraction tasks)"
        if collect_media == "images":
            collect_context += "\n  (Only image search, no video extraction)"
        elif collect_media == "videos":
            collect_context += "\n  (Only video extraction, no image search)"

        prompt = f"""
        You are the Planner for an autonomous Product Research Agent.
        Your goal is to gather comprehensive information and images about a product.

        Current State:
        - Query: {state.get("query")}
        - Product Identified: {bool(state.get("product"))}
        - Specifications Found: {list(state.get("specifications", {}).keys())}
        - Missing Views: {state.get("missing_views", [])}
        - Images Collected: {len(state.get("images", []))}
        - Videos Processed: {len(state.get("videos", []))}
        - Failed Tasks: {len(state.get("failed_tasks", []))}{focus_context}{collect_context}

        Decide what tasks to execute next.
        If the product is not identified, output a 'discover' task.
        If missing views and few images collected, output 'find_images' tasks.
        If missing views and image search is slow,
        try 'find_videos' to extract from YouTube reviews.
        If the product is identified but lacks specs, output 'verify_spec'.
        """

        try:
            result = llm.invoke(prompt)
            new_tasks = [t.model_dump() for t in result.tasks]
            self.logger.info("Planner generated %d tasks", len(new_tasks))
            return {"tasks": new_tasks, "iterations": iterations}
        except Exception as e:
            self.logger.warning("Planner LLM failed: %s", e)
            return self._fallback_tasks(state, iterations, focus)

    def _fallback_tasks(self, state: dict, iterations: int, focus: FocusConfig | None = None) -> dict:
        """Generate fallback tasks when LLM fails."""
        collect_specs = self._can_collect_specs(state)
        collect_media = self._can_collect_media(state)

        if not state.get("product"):
            return {
                "tasks": [{"type": "discover", "target": state.get("query", ""), "priority": 1.0}],
                "iterations": iterations,
            }

        # No specs mode - skip verify_spec tasks
        if not collect_specs:
            if collect_media == "images" and state.get("missing_views"):
                return {
                    "tasks": [{"type": "find_images", "target": state.get("missing_views")[0], "priority": 0.9}],
                    "iterations": iterations,
                }
            elif collect_media == "videos" and state.get("missing_views"):
                return {
                    "tasks": [{"type": "find_videos", "target": state.get("missing_views")[0], "priority": 0.9}],
                    "iterations": iterations,
                }
            elif collect_media == "both" and state.get("missing_views"):
                return {
                    "tasks": [{"type": "find_images", "target": state.get("missing_views")[0], "priority": 0.9}],
                    "iterations": iterations,
                }
            return {"tasks": [], "iterations": iterations}

        # Specs mode only - no media tasks
        if collect_media is None:
            if len(state.get("specifications", {})) < 5:
                return {
                    "tasks": [{"type": "verify_spec", "target": "general", "priority": 0.9}],
                    "iterations": iterations,
                }
            return {"tasks": [], "iterations": iterations}

        # Full mode - both specs and media
        has_youtube_focus = focus and FocusArea.YOUTUBE in focus.areas
        has_specs_focus = focus and FocusArea.SPECS in focus.areas

        if state.get("missing_views"):
            images_count = len(state.get("images", []))

            # Videos only
            if collect_media == "videos":
                return {
                    "tasks": [{"type": "find_videos", "target": state.get("missing_views")[0], "priority": 0.9}],
                    "iterations": iterations,
                }

            # Images only or both
            if has_youtube_focus and collect_media == "both" and images_count < 5:
                return {
                    "tasks": [{"type": "find_videos", "target": state.get("missing_views")[0], "priority": 0.9}],
                    "iterations": iterations,
                }

            if images_count < 3:
                return {
                    "tasks": [{"type": "find_images", "target": state.get("missing_views")[0], "priority": 0.9}],
                    "iterations": iterations,
                }
            elif collect_media == "both":
                return {
                    "tasks": [{"type": "find_videos", "target": state.get("missing_views")[0], "priority": 0.8}],
                    "iterations": iterations,
                }

        if has_specs_focus and len(state.get("specifications", {})) < 3:
            return {
                "tasks": [{"type": "verify_spec", "target": "general", "priority": 0.9}],
                "iterations": iterations,
            }

        return {
            "tasks": [{"type": "verify_spec", "target": "general", "priority": 0.8}],
            "iterations": iterations,
        }
