"""Coverage agent - evaluate what is missing and decide if more research is needed."""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.config.logging import get_logger
from src.search.focus import FocusArea, FocusConfig

logger = get_logger(__name__)


class CoverageAgent(BaseAgent):
    """Coverage Agent - evaluates gap analysis and routes to next step."""

    name = "coverage"

    def _get_focus(self, state: dict) -> FocusConfig:
        """Extract FocusConfig from state."""
        return FocusConfig.from_dict(state.get("focus_config", {}))

    def analyze(self, state: dict) -> dict:
        """Evaluate what is missing from both image search and video extraction."""
        self.logger.info("Coverage agent executing")

        required_views = state.get("required_views", [])
        discovered_views = state.get("discovered_views", {})
        focus = self._get_focus(state)

        missing_views = [v for v in required_views if v not in discovered_views]

        # Focus-aware completeness check
        has_youtube_focus = focus and FocusArea.YOUTUBE in focus.areas
        has_specs_focus = focus and FocusArea.SPECS in focus.areas

        # If YouTube is focused, require at least one video source
        if has_youtube_focus:
            video_images = [
                img for img in state.get("images", [])
                if img.get("source") == "video"
            ]
            if not video_images and missing_views:
                # Force at least one video extraction attempt
                if "find_videos" not in [t.get("type") for t in state.get("tasks", [])]:
                    self.logger.info("YouTube focus: forcing video extraction")

        # If specs are focused, check specification count
        if has_specs_focus:
            specs = state.get("specifications", {})
            if len(specs) < 3:
                # Allow more iterations for spec collection
                status = "incomplete" if missing_views or len(specs) < 5 else "complete"
            else:
                status = "complete" if not missing_views else "incomplete"
        else:
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
