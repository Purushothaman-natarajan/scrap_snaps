"""Coverage agent - evaluate what is missing and decide if more research is needed."""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.config.logging import get_logger

logger = get_logger(__name__)


class CoverageAgent(BaseAgent):
    """Coverage Agent - evaluates gap analysis and routes to next step."""

    name = "coverage"

    def analyze(self, state: dict) -> dict:
        """Evaluate what is missing from both image search and video extraction."""
        self.logger.info("Coverage agent executing")

        required_views = state.get("required_views", [])
        discovered_views = state.get("discovered_views", {})

        missing_views = [v for v in required_views if v not in discovered_views]

        status = "complete" if not missing_views else "incomplete"

        images_count = len(state.get("images", []))
        videos_count = len(state.get("videos", []))
        self.logger.info(
            "Coverage: %d/%d views found, %d images, %d videos",
            len(required_views) - len(missing_views),
            len(required_views),
            images_count,
            videos_count,
        )

        return {"missing_views": missing_views, "status": status}

    def route(self, state: dict) -> str:
        """Route after coverage analysis."""
        if state.get("status") == "max_iterations_reached":
            return "complete"
        if state.get("status") == "incomplete":
            return "more_research"
        return "complete"
