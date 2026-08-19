"""Planner agent - LLM-powered task generation with dedup and iteration control.

The planner generates research tasks (discover, find_images, find_videos, verify_spec)
based on current state. It includes:

- LLM-based task dedup: asks the LLM if new tasks are meaningfully different from
  previous attempts. If not, returns "partial_complete" to terminate the loop.
- Deterministic fingerprint fallback: if LLM dedup fails, compares task fingerprints.
- Failed URL awareness: skips scheduling tasks that would retry known-failed URLs.
- Focus-aware task selection: respects collect_specs, collect_media, and focus_areas.
"""

from __future__ import annotations

import hashlib
import json

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


class DedupOutput(BaseModel):
    """Structured output for task dedup check."""

    is_different: bool = Field(
        description="True if the new tasks are meaningfully different from previous attempts"
    )
    reason: str = Field(description="Brief explanation of why tasks are different or not")


def _fingerprint_tasks(tasks: list[dict]) -> str:
    """Compute a deterministic fingerprint for a set of tasks."""
    task_tuples = sorted(
        (t.get("type", ""), t.get("target", "")) for t in tasks
    )
    raw = json.dumps(task_tuples, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


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
            # Fingerprint existing tasks and check for circulating duplicates
            fp = _fingerprint_tasks(tasks)
            previous_fingerprints = state.get("previous_task_fingerprints", [])
            fp_count = previous_fingerprints.count(fp)
            if fp_count >= 2:
                self.logger.warning(
                    "Same tasks fingerprint seen %d times, marking partial_complete", fp_count
                )
                return {
                    "status": "partial_complete",
                    "tasks": [],
                    "iterations": iterations,
                }
            return {
                "tasks": tasks,
                "previous_task_fingerprints": previous_fingerprints + [fp],
                "iterations": iterations,
            }

        llm = self.get_llm().with_structured_output(PlannerOutput)
        focus = self._get_focus(state)
        collect_specs = self._can_collect_specs(state)
        collect_media = self._can_collect_media(state)
        failed_media_urls = state.get("failed_media_urls", [])
        previous_fingerprints = state.get("previous_task_fingerprints", [])

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

        # Build failure context
        failure_context = ""
        if failed_media_urls:
            failure_context = (
                f"\n- Failed Media URLs: {len(failed_media_urls)} URLs "
                f"(403/bot-detection). DO NOT retry these URLs."
            )

        # Build dedup context
        dedup_context = ""
        if previous_fingerprints:
            recent = previous_fingerprints[-5:]
            dedup_context = (
                f"\n- Previous task cycles: {len(previous_fingerprints)} "
                f"(recent fingerprints: {recent}). "
                f"Your new tasks MUST be meaningfully different from these."
            )

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
        - Failed Tasks: {len(state.get("failed_tasks", []))}{focus_context}{collect_context}{failure_context}{dedup_context}

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

            # LLM-based dedup check
            if previous_fingerprints and new_tasks:
                is_different = self._check_tasks_different(
                    llm, new_tasks, previous_fingerprints, state
                )
                if not is_different:
                    self.logger.warning(
                        "Planner generated duplicate tasks, marking partial_complete"
                    )
                    return {
                        "status": "partial_complete",
                        "tasks": [],
                        "iterations": iterations,
                    }

            # Compute fingerprint for this cycle
            fp = _fingerprint_tasks(new_tasks)
            updated_fingerprints = previous_fingerprints + [fp]

            self.logger.info("Planner generated %d tasks", len(new_tasks))
            return {
                "tasks": new_tasks,
                "previous_task_fingerprints": updated_fingerprints,
                "iterations": iterations,
            }
        except Exception as e:
            self.logger.warning("Planner LLM failed: %s", e)
            return self._fallback_tasks(state, iterations, focus)

    def _check_tasks_different(
        self,
        llm,
        new_tasks: list[dict],
        previous_fingerprints: list[str],
        state: dict,
    ) -> bool:
        """Use LLM to check if new tasks are meaningfully different from previous attempts."""
        try:
            dedup_llm = self.get_llm().with_structured_output(DedupOutput)

            prompt = f"""
            Are these new research tasks meaningfully different from previous failed attempts?

            New tasks: {json.dumps(new_tasks, indent=2)}

            Previous task fingerprints (last 3): {previous_fingerprints[-3:]}

            Failed media URLs (DO NOT retry these): {state.get("failed_media_urls", [])[:10]}

            Consider:
            - Are the task types different? (e.g., find_images vs find_videos)
            - Are the targets different? (e.g., 'front' vs 'side')
            - Would these tasks likely hit the same failed URLs?

            Reply with is_different=true if tasks are meaningfully different.
            Reply with is_different=false if tasks would likely repeat failed attempts.
            """
            result = dedup_llm.invoke(prompt)
            return result.is_different
        except Exception as e:
            self.logger.warning("Dedup check failed, using fingerprint comparison: %s", e)
            # Fallback: deterministic fingerprint comparison
            fp = _fingerprint_tasks(new_tasks)
            return fp not in previous_fingerprints

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
        failed_media_urls = state.get("failed_media_urls", [])

        if state.get("missing_views"):
            images_count = len(state.get("images", []))

            # Videos only
            if collect_media == "videos":
                if failed_media_urls:
                    self.logger.warning("All video URLs failed, cannot collect videos")
                    return {"tasks": [], "iterations": iterations}
                return {
                    "tasks": [{"type": "find_videos", "target": state.get("missing_views")[0], "priority": 0.9}],
                    "iterations": iterations,
                }

            # Images only or both
            if has_youtube_focus and collect_media == "both" and images_count < 5:
                if not failed_media_urls:
                    return {
                        "tasks": [{"type": "find_videos", "target": state.get("missing_views")[0], "priority": 0.9}],
                        "iterations": iterations,
                    }

            if images_count < 3:
                return {
                    "tasks": [{"type": "find_images", "target": state.get("missing_views")[0], "priority": 0.9}],
                    "iterations": iterations,
                }
            elif collect_media == "both" and not failed_media_urls:
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
