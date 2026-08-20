"""Media collection agent — handles image and video acquisition.

Supports 7 collect modes: images, videos, video_urls, video_frames,
images_and_video_urls, both, none.

Features:
- Failed URL filtering: checks state["failed_media_urls"] before downloading,
  skips URLs that previously returned 403/bot-detection.
- Failure propagation: appends failed URLs to state so the planner knows not to
  retry them.
- Standardized filenames: uses naming convention row_{ROW}_{product}_{view}_{hash}.
- Focus-aware queries: uses the query builder with focus areas.
- Configurable limits: IMAGE_DOWNLOAD_LIMIT, IMAGE_CROP_RATIO, SEARCH_QUERIES_PER_TASK,
  VIDEO_MAX_FRAMES_PER_VIEW — all from settings.
- Video modes: "video_urls" returns URLs only (no download), "video_frames"
  skips AI frame selection, "videos" runs full pipeline.
"""

from __future__ import annotations

import os

from src.agents.base import BaseAgent
from src.config import (
    AI_FRAME_SELECTION,
    CROP_VIDEO_FRAMES,
    DOWNLOAD_DIR,
    IMAGE_CROP_RATIO,
    IMAGE_DOWNLOAD_LIMIT,
    MAX_IMAGE_RESULTS,
    REQUIRED_VIEWS,
    SEARCH_QUERIES_PER_TASK,
    VIDEO_DOWNLOAD_DIR,
    VIDEO_MAX_FRAMES_PER_VIEW,
)
from src.config.logging import get_logger
from src.search.focus import FocusConfig
from src.search.query_builder import build_queries
from src.tools.media.images import (
    analyze_images_batch,
    deduplicate_images,
    download_image,
)
from src.tools.media.video import (
    download_video,
    extract_frames,
    score_video,
    select_best_frames,
)
from src.tools.utils.failed_urls import get_failed_url_tracker
from src.tools.web import search_images, search_videos
from src.tools.web.cache import get_search_cache

logger = get_logger(__name__)

DEFAULT_TARGET_VIEW = "front"


def _slugify_query(text: str, max_len: int = 40) -> str:
    """Convert query text to a filesystem-safe slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    return text[:max_len].rstrip("_")


def _short_hash(text: str, length: int = 6) -> str:
    """Generate a short hash from text."""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:length]


def _crop_center(image_path: str, crop_ratio: float | None = None) -> str | None:
    """Crop the center region of an image to focus on the product.

    Crops to the central ``crop_ratio`` of both width and height.
    Returns the cropped image path, or None on failure.
    """
    if crop_ratio is None:
        crop_ratio = IMAGE_CROP_RATIO
    try:
        from PIL import Image

        img = Image.open(image_path)
        w, h = img.size

        new_w = int(w * crop_ratio)
        new_h = int(h * crop_ratio)
        left = (w - new_w) // 2
        top = (h - new_h) // 2
        right = left + new_w
        bottom = top + new_h

        cropped = img.crop((left, top, right, bottom))

        crop_path = image_path.replace(".jpg", "_crop.jpg").replace(".png", "_crop.png")
        cropped.save(crop_path, quality=95)
        return crop_path
    except Exception as e:
        logger.warning("Failed to crop image %s: %s", image_path, e)
        return None


class MediaAgent(BaseAgent):
    """Media Agent - searches, downloads, and classifies product images and videos."""

    name = "media_collector"

    def _get_focus(self, state: dict) -> FocusConfig:
        """Extract FocusConfig from state."""
        return FocusConfig.from_dict(state.get("focus_config", {}))

    def _can_collect_media(self, state: dict) -> str:
        """Check what media we should collect: images, videos, or both."""
        return state.get("collect_media", "images_and_video_urls")

    def collect_images(self, state: dict) -> dict:
        """Image search -> download -> deduplicate -> classify views."""
        collect_media = self._can_collect_media(state)
        if collect_media == "videos":
            self.logger.info("Skipping image collection (collect_media=videos)")
            tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_images")
            return {"tasks": tasks}

        self.logger.info("Media agent: collecting images")
        product = state.get("product", {})
        query = product.get("name", state.get("query", ""))
        focus = self._get_focus(state)
        tracker = get_failed_url_tracker()
        row_index = state.get("__row_index", 0)

        tasks = state.get("tasks", [])
        target_view = DEFAULT_TARGET_VIEW
        for t in tasks:
            if t.get("type") == "find_images":
                target_view = t.get("target")
                break

        queries = build_queries(
            query, focus=focus, task_type="find_images", limit=SEARCH_QUERIES_PER_TASK
        )
        if queries:
            search_q = queries[0].query
        else:
            search_q = f"{query} {target_view} view high quality"

        results = search_images.invoke({"query": search_q, "limit": MAX_IMAGE_RESULTS})

        images_list = state.get("images", [])
        discovered_views = state.get("discovered_views", {})

        if results:
            # Phase 1: Download and collect all candidate paths
            existing_urls = {img.get("url", "") for img in images_list}
            new_paths = []
            new_urls = []
            for res in results[:IMAGE_DOWNLOAD_LIMIT]:
                img_url = res.get("url")

                if img_url in existing_urls:
                    self.logger.debug("Skipping already-collected image URL: %s", img_url)
                    continue

                if tracker.is_failed(img_url):
                    self.logger.debug("Skipping previously failed image URL: %s", img_url)
                    continue

                view_hint = target_view or "unknown"
                img_filename = (
                    f"row_{row_index}_{_slugify_query(query)}_{view_hint}"
                    f"_{_short_hash(img_url)}.jpg"
                )
                local_path = download_image.invoke({
                    "url": img_url,
                    "save_dir": DOWNLOAD_DIR,
                    "filename": img_filename,
                })

                if local_path:
                    new_paths.append(local_path)
                    new_urls.append(img_url)

            if new_paths:
                # Phase 2: Deduplicate against existing images
                existing_paths = [img["local_path"] for img in images_list]
                all_paths = existing_paths + new_paths
                unique_paths = deduplicate_images.invoke({"image_paths": all_paths})
                unique_set = set(unique_paths)

                # Phase 3: Collect only truly new unique images for batch analysis
                paths_to_analyze = []
                urls_for_paths = []
                for path, url in zip(new_paths, new_urls):
                    if path in unique_set and path not in existing_paths:
                        paths_to_analyze.append(path)
                        urls_for_paths.append(url)
                    elif path not in unique_set:
                        self.logger.info("Skipped duplicate image: %s", path)

                # Phase 4: Batch analyze all new unique images (1 LLM call)
                if paths_to_analyze:
                    self.logger.info("Batch analyzing %d new images", len(paths_to_analyze))
                    analyses = analyze_images_batch.invoke({"image_paths": paths_to_analyze})

                    for path, url, analysis in zip(paths_to_analyze, urls_for_paths, analyses):
                        view_type = analysis.get("view", "unknown")
                        confidence = analysis.get("confidence", 0.0)
                        product_match = analysis.get("product_match", False)

                        if product_match:
                            images_list.append({
                                "url": url,
                                "local_path": path,
                                "view": view_type,
                                "confidence": confidence,
                            })

                            if view_type not in discovered_views:
                                discovered_views[view_type] = []
                            discovered_views[view_type].append(path)

        # Sync failed URLs back to state for planner awareness
        failed_urls = list(tracker.get_all())
        tasks = self.remove_tasks_by_type(tasks, "find_images")
        return {
            "images": images_list,
            "discovered_views": discovered_views,
            "failed_media_urls": failed_urls,
            "tasks": tasks,
            "serpapi_budget_remaining": get_search_cache().remaining(),
        }

    def collect_videos(self, state: dict) -> dict:
        """Search YouTube -> download -> extract frames -> classify views.

        Handles multiple video modes:
        - "videos": full pipeline (download → extract → classify → AI select)
        - "video_urls": search only, return URLs
        - "video_frames": download + extract + classify, skip AI frame selection
        - "images_and_video_urls": search only, return URLs (images handled separately)
        """
        collect_media = self._can_collect_media(state)

        if collect_media == "images":
            self.logger.info("Skipping video collection (collect_media=images)")
            tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
            return {"tasks": tasks}

        # URL-only modes: search but don't download
        if collect_media in ("video_urls", "images_and_video_urls"):
            return self._collect_video_urls(state)

        self.logger.info("Media agent: collecting videos")

        product = state.get("product", {})
        query = product.get("name", state.get("query", ""))
        missing_views = state.get("missing_views", REQUIRED_VIEWS.copy())
        focus = self._get_focus(state)
        tracker = get_failed_url_tracker()
        row_index = state.get("__row_index", 0)

        queries = build_queries(
            query, focus=focus, task_type="find_videos", limit=SEARCH_QUERIES_PER_TASK
        )
        if queries:
            search_q = queries[0].query
        else:
            search_q = f"{query} review angles"

        videos = search_videos.invoke({"query": search_q, "limit": 10})

        if not videos:
            self.logger.warning("No videos found for query: %s", query)
            tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
            return {"tasks": tasks}

        for v in videos:
            v["score"] = score_video(v)
        videos.sort(key=lambda v: v.get("score", 0), reverse=True)

        from src.config import MAX_VIDEO_RESULTS
        selected_videos = videos[:MAX_VIDEO_RESULTS]
        self.logger.info("Selected %d videos for processing", len(selected_videos))

        images_list = state.get("images", [])
        discovered_views = state.get("discovered_views", {})
        existing_video_urls = {v.get("url", "") for v in state.get("videos", [])}
        all_frame_paths = []

        for video_info in selected_videos:
            url = video_info.get("url", "")

            if url in existing_video_urls:
                self.logger.debug("Skipping already-collected video URL: %s", url)
                continue

            if tracker.is_failed(url):
                self.logger.debug("Skipping previously failed video URL: %s", url)
                continue

            self.logger.info("Processing video: %s", video_info.get("title", url))

            # Build standardized filename using naming convention
            vid_filename = f"row_{row_index}_{_slugify_query(query)}_{_short_hash(url)}.mp4"
            video_path = download_video.invoke({
                "url": url,
                "save_dir": VIDEO_DOWNLOAD_DIR,
                "filename": vid_filename,
            })
            if not video_path:
                self.logger.warning("Failed to download video: %s", url)
                continue

            video_name = os.path.basename(video_path).split(".")[0]
            frames_dir = os.path.join(DOWNLOAD_DIR, "frames", video_name)
            frame_paths = extract_frames.invoke(
                {"video_path": video_path, "output_dir": frames_dir}
            )
            all_frame_paths.extend(frame_paths)

            try:
                os.remove(video_path)
                self.logger.info("Deleted video file: %s", video_path)
            except OSError as e:
                self.logger.warning("Failed to delete video %s: %s", video_path, e)

        if not all_frame_paths:
            self.logger.warning("No frames extracted from any video")
            tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
            failed_urls = list(tracker.get_all())
            return {"failed_media_urls": failed_urls, "tasks": tasks}

        self.logger.info("Deduplicating %d frames", len(all_frame_paths))
        unique_paths = deduplicate_images.invoke({"image_paths": all_frame_paths})
        self.logger.info("Kept %d unique frames after dedup", len(unique_paths))

        if CROP_VIDEO_FRAMES and unique_paths:
            self.logger.info("Cropping %d video frames to center region", len(unique_paths))
            cropped_paths = []
            for fp in unique_paths:
                cropped = _crop_center(fp)
                if cropped:
                    cropped_paths.append(cropped)
                else:
                    cropped_paths.append(fp)
            unique_paths = cropped_paths

        self.logger.info("Classifying view types for %d frames", len(unique_paths))

        # Batch analyze all frames (1 LLM call instead of N)
        analyses = analyze_images_batch.invoke({"image_paths": unique_paths})

        for frame_path, analysis in zip(unique_paths, analyses):
            if analysis.get("product_match", False):
                view_type = analysis.get("view", "unknown")
                confidence = analysis.get("confidence", 0.0)

                images_list.append({
                    "url": f"video://{frame_path}",
                    "local_path": frame_path,
                    "view": view_type,
                    "confidence": confidence,
                    "source": "video",
                })

                if view_type not in discovered_views:
                    discovered_views[view_type] = []
                discovered_views[view_type].append(frame_path)

        use_ai_selection = AI_FRAME_SELECTION and collect_media != "video_frames"
        if use_ai_selection and images_list:
            self.logger.info("Running AI frame selection")
            video_frame_paths = [
                img["local_path"] for img in images_list if img.get("source") == "video"
            ]
            selected = select_best_frames.invoke({
                "frame_paths": video_frame_paths,
                "views": missing_views,
                "max_per_view": VIDEO_MAX_FRAMES_PER_VIEW,
            })

            video_frames: dict[str, list[str]] = {}
            for view, frames in selected.items():
                video_frames[view] = [f["path"] for f in frames if f.get("path")]

            # Sync failed URLs back to state for planner awareness
            failed_urls = list(tracker.get_all())
            tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
            return {
                "images": images_list,
                "discovered_views": discovered_views,
                "video_frames": video_frames,
                "failed_media_urls": failed_urls,
                "tasks": tasks,
                "serpapi_budget_remaining": get_search_cache().remaining(),
            }

        # Sync failed URLs back to state for planner awareness
        failed_urls = list(tracker.get_all())
        tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
        return {
            "images": images_list,
            "discovered_views": discovered_views,
            "failed_media_urls": failed_urls,
            "tasks": tasks,
            "serpapi_budget_remaining": get_search_cache().remaining(),
        }

    def _collect_video_urls(self, state: dict) -> dict:
        """Search YouTube for videos and return URLs only (no download/processing)."""
        self.logger.info("Media agent: collecting video URLs only")

        product = state.get("product", {})
        query = product.get("name", state.get("query", ""))
        focus = self._get_focus(state)

        queries = build_queries(
            query, focus=focus, task_type="find_videos", limit=SEARCH_QUERIES_PER_TASK
        )
        if queries:
            search_q = queries[0].query
        else:
            search_q = f"{query} review angles"

        videos = search_videos.invoke({"query": search_q, "limit": 10})

        if not videos:
            self.logger.warning("No videos found for query: %s", query)
            tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
            return {"tasks": tasks}

        for v in videos:
            v["score"] = score_video(v)
        videos.sort(key=lambda v: v.get("score", 0), reverse=True)

        from src.config import MAX_VIDEO_RESULTS
        selected_videos = videos[:MAX_VIDEO_RESULTS]

        video_list = state.get("videos", [])
        for v in selected_videos:
            video_list.append({
                "url": v.get("url", ""),
                "title": v.get("title", ""),
                "duration": v.get("duration", 0),
                "score": v.get("score", 0.0),
            })

        tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
        return {
            "videos": video_list,
            "tasks": tasks,
            "serpapi_budget_remaining": get_search_cache().remaining(),
        }
