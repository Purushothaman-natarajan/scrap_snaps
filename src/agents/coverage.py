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

    def _can_collect_specs(self, state: dict) -> bool:
        """Check if we should collect specs."""
        return state.get("collect_specs", True)

    def _can_collect_media(self, state: dict) -> str:
        """Check what media we should collect: images, videos, or both."""
        return state.get("collect_media", "both")

    def analyze(self, state: dict) -> dict:
        """Evaluate what is missing based on collect mode."""
        self.logger.info("Coverage agent executing")

        collect_specs = self._can_collect_specs(state)
        collect_media = self._can_collect_media(state)
        focus = self._get_focus(state)

        required_views = state.get("required_views", [])
        discovered_views = state.get("discovered_views", {})
        missing_views = [v for v in required_views if v not in discovered_views]

        specs = state.get("specifications", {})
        images_count = len(state.get("images", []))
        videos_count = len(state.get("videos", []))

        # No specs mode - skip spec requirements
        if not collect_specs:
            if collect_media == "videos":
                status = "complete" if videos_count >= 2 else "incomplete"
                self.logger.info("Coverage (videos only): %d videos", videos_count)
                return {"missing_views": [], "status": status}

            if collect_media == "images":
                status = "complete" if not missing_views else "incomplete"
                self.logger.info(
                    "Coverage (images only): %d/%d views found",
                    len(required_views) - len(missing_views),
                    len(required_views),
                )
                return {"missing_views": missing_views, "status": status}

            # Both images+videos, no specs
            status = "complete" if not missing_views else "incomplete"
            self.logger.info(
                "Coverage (media only): %d/%d views found",
                len(required_views) - len(missing_views),
                len(required_views),
            )
            return {"missing_views": missing_views, "status": status}

        # Specs mode, no media
        if collect_media is None:
            status = "complete" if len(specs) >= 5 else "incomplete"
            self.logger.info("Coverage (specs only): %d specs collected", len(specs))
            return {"missing_views": [], "status": status}

        # Full mode - both specs and media
        has_youtube_focus = focus and FocusArea.YOUTUBE in focus.areas
        has_specs_focus = focus and FocusArea.SPECS in focus.areas

        if has_youtube_focus:
            video_images = [
                img for img in state.get("images", [])
                if img.get("source") == "video"
            ]
            if not video_images and missing_views:
                if "find_videos" not in [t.get("type") for t in state.get("tasks", [])]:
                    self.logger.info("YouTube focus: forcing video extraction")

        if has_specs_focus:
            if len(specs) < 3:
                status = "incomplete" if missing_views or len(specs) < 5 else "complete"
            else:
                status = "complete" if not missing_views else "incomplete"
        else:
            status = "complete" if not missing_views else "incomplete"

        self.logger.info(
            "Coverage: %d/%d views found, %d specs, %d images, %d videos",
            len(required_views) - len(missing_views),
            len(required_views),
            len(specs),
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
