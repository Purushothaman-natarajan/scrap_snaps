"""Coverage agent — evaluate completeness and decide if more research is needed.

The coverage agent evaluates gap analysis and routes the graph. All thresholds
are configurable via settings.

Features:
- Hard cycle limit: forces termination after COVERAGE_MAX_CYCLES coverage checks
  to prevent infinite loops even when new data trickles in.
- Threshold-based no-progress: considers "no progress" if total new items added
  since last check is <= COVERAGE_NO_PROGRESS_THRESHOLD (default 1).
- Iterations proximity check: forces termination when iterations approaches
  max_iterations (COVERAGE_PROXIMITY_RATIO, default 80%).
- YouTube failure handling: if all video URLs failed (bot detection), does not
  force video extraction — continues with images/specs only.
- Focus-aware evaluation: respects collect_specs, collect_media (7 modes),
  and focus areas.
"""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.config import (
    COVERAGE_MAX_CYCLES,
    COVERAGE_NO_PROGRESS_THRESHOLD,
    COVERAGE_PROXIMITY_RATIO,
)
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
        return state.get("collect_media", "images_and_video_urls")

    def _is_no_progress(self, state: dict) -> bool:
        """Check if no meaningful new data was collected since last coverage check.

        Uses a threshold: considers "no progress" if the total number of new items
        (images + specs + views) added since the last check is <= NO_PROGRESS_THRESHOLD.
        This is more robust than exact equality, which can miss cases where 1 item
        trickles in each cycle.
        """
        current_images = len(state.get("images", []))
        current_specs = len(state.get("specifications", {}))
        current_views = len(state.get("discovered_views", {}))

        prev_images = state.get("_prev_images_count", 0)
        prev_specs = state.get("_prev_specs_count", 0)
        prev_views = state.get("_prev_views_count", 0)

        total_current = current_images + current_specs + current_views
        total_prev = prev_images + prev_specs + prev_views

        if total_current == 0:
            return False

        new_items = total_current - total_prev
        return new_items <= COVERAGE_NO_PROGRESS_THRESHOLD

    def _snapshot_progress(self, state: dict) -> dict:
        """Return state updates to snapshot current progress."""
        return {
            "_prev_images_count": len(state.get("images", [])),
            "_prev_specs_count": len(state.get("specifications", {})),
            "_prev_views_count": len(state.get("discovered_views", {})),
        }

    def analyze(self, state: dict) -> dict:
        """Evaluate what is missing based on collect mode."""
        self.logger.info("Coverage agent executing")

        collect_specs = self._can_collect_specs(state)
        collect_media = self._can_collect_media(state)
        focus = self._get_focus(state)
        failed_media_urls = state.get("failed_media_urls", [])

        required_views = state.get("required_views", [])
        discovered_views = state.get("discovered_views", {})
        missing_views = [v for v in required_views if v not in discovered_views]

        specs = state.get("specifications", {})
        images_count = len(state.get("images", []))
        videos_count = len(state.get("videos", []))

        # Increment coverage cycle counter
        coverage_cycles = state.get("_coverage_cycles", 0) + 1
        updates = self._snapshot_progress(state)
        updates["_coverage_cycles"] = coverage_cycles

        # Hard cycle limit - force termination
        if coverage_cycles >= COVERAGE_MAX_CYCLES:
            self.logger.warning(
                "Coverage hard limit reached (%d cycles). Forcing termination.",
                coverage_cycles,
            )
            updates["status"] = "partial_complete"
            updates["missing_views"] = missing_views
            return updates

        # Check for no-progress (threshold-based)
        no_progress = self._is_no_progress(state)

        if no_progress:
            self.logger.warning(
                "No new data collected since last check (%d images, %d specs, %d views). "
                "Marking as partial_complete.",
                images_count,
                len(specs),
                len(discovered_views),
            )
            updates["status"] = "partial_complete"
            updates["missing_views"] = missing_views
            return updates

        # No specs mode - skip spec requirements
        if not collect_specs:
            if collect_media in ("videos", "video_urls", "video_frames"):
                status = "complete" if videos_count >= 2 else "incomplete"
                self.logger.info("Coverage (videos only): %d videos", videos_count)
                updates["missing_views"] = []
                updates["status"] = status
                return updates

            if collect_media == "images_and_video_urls":
                status = "complete" if not missing_views else "incomplete"
                self.logger.info(
                    "Coverage (images + video_urls): %d/%d views found",
                    len(required_views) - len(missing_views),
                    len(required_views),
                )
                updates["missing_views"] = missing_views
                updates["status"] = status
                return updates

            if collect_media == "images":
                status = "complete" if not missing_views else "incomplete"
                self.logger.info(
                    "Coverage (images only): %d/%d views found",
                    len(required_views) - len(missing_views),
                    len(required_views),
                )
                updates["missing_views"] = missing_views
                updates["status"] = status
                return updates

            # Both images+videos, no specs
            # If all video URLs failed and no video-sourced images, treat as images-only
            if failed_media_urls and videos_count == 0:
                status = "complete" if not missing_views else "incomplete"
                self.logger.info(
                    "Coverage (media, videos failed): %d/%d views found",
                    len(required_views) - len(missing_views),
                    len(required_views),
                )
                updates["missing_views"] = missing_views
                updates["status"] = status
                return updates

            status = "complete" if not missing_views else "incomplete"
            self.logger.info(
                "Coverage (media only): %d/%d views found",
                len(required_views) - len(missing_views),
                len(required_views),
            )
            updates["missing_views"] = missing_views
            updates["status"] = status
            return updates

        # Specs mode, no media
        if collect_media is None or collect_media == "none":
            status = "complete" if len(specs) >= 5 else "incomplete"
            self.logger.info("Coverage (specs only): %d specs collected", len(specs))
            updates["missing_views"] = []
            updates["status"] = status
            return updates

        # Full mode - both specs and media
        has_youtube_focus = focus and FocusArea.YOUTUBE in focus.areas
        has_specs_focus = focus and FocusArea.SPECS in focus.areas

        # YouTube focus: only force video extraction if collect_media allows it
        # Respects config.yaml `collect_media` (e.g. images_and_video_urls, images, none)
        if has_youtube_focus and collect_media not in (None, "none", "images"):
            video_images = [
                img for img in state.get("images", [])
                if img.get("source") == "video"
            ]
            # If all video downloads failed, don't force video extraction
            if failed_media_urls and not video_images:
                self.logger.info(
                    "YouTube focus: all video URLs failed (%d failed), "
                    "continuing without video extraction",
                    len(failed_media_urls),
                )
            elif not video_images and missing_views:
                if "find_videos" not in [t.get("type") for t in state.get("tasks", [])]:
                    self.logger.info("YouTube focus: forcing video extraction")
        elif has_youtube_focus and collect_media in (None, "none", "images"):
            self.logger.info(
                "YouTube focus ignored — collect_media=%s does not allow video",
                collect_media,
            )

        if has_specs_focus:
            if len(specs) < 3:
                status = "incomplete" if missing_views or len(specs) < 5 else "complete"
            else:
                status = "complete" if not missing_views else "incomplete"
        else:
            status = "complete" if not missing_views else "incomplete"

        self.logger.info(
            "Coverage: %d/%d views found, %d specs, %d images, %d videos (cycle %d/%d)",
            len(required_views) - len(missing_views),
            len(required_views),
            len(specs),
            images_count,
            videos_count,
            coverage_cycles,
            COVERAGE_MAX_CYCLES,
        )

        updates["missing_views"] = missing_views
        updates["status"] = status
        return updates

    def route(self, state: dict) -> str:
        """Route after coverage analysis."""
        status = state.get("status")
        if status in ("max_iterations_reached", "partial_complete"):
            return "complete"
        if status == "incomplete":
            # Safety check: force complete if iterations is near max
            iterations = state.get("iterations", 0)
            max_iterations = state.get("max_iterations", 30)
            if iterations >= max_iterations * COVERAGE_PROXIMITY_RATIO:
                self.logger.warning(
                    "Iterations proximity check: %d/%d. Forcing complete.",
                    iterations,
                    max_iterations,
                )
                return "complete"
            return "more_research"
        return "complete"
