"""Media collection agent - handles image and video acquisition."""

from __future__ import annotations

import os

from src.agents.base import BaseAgent
from src.config import (
    AI_FRAME_SELECTION,
    DOWNLOAD_DIR,
    MAX_IMAGE_RESULTS,
    REQUIRED_VIEWS,
    VIDEO_DOWNLOAD_DIR,
)
from src.config.logging import get_logger
from src.tools.media.images import analyze_image, deduplicate_images, download_image
from src.tools.media.video import (
    download_video,
    extract_frames,
    score_video,
    select_best_frames,
)
from src.tools.web import search_images, search_videos

logger = get_logger(__name__)

DEFAULT_TARGET_VIEW = "front"


class MediaAgent(BaseAgent):
    """Media Agent - searches, downloads, and classifies product images and videos."""

    name = "media_collector"

    def collect_images(self, state: dict) -> dict:
        """Image search -> download -> deduplicate -> classify views."""
        self.logger.info("Media agent: collecting images")
        product = state.get("product", {})
        query = product.get("name", state.get("query", ""))

        tasks = state.get("tasks", [])
        target_view = DEFAULT_TARGET_VIEW
        for t in tasks:
            if t.get("type") == "find_images":
                target_view = t.get("target")
                break

        search_q = f"{query} {target_view} view high quality"
        results = search_images.invoke({"query": search_q, "limit": MAX_IMAGE_RESULTS})

        images_list = state.get("images", [])
        discovered_views = state.get("discovered_views", {})

        if results:
            for res in results[:2]:
                img_url = res.get("url")
                local_path = download_image.invoke({"url": img_url, "save_dir": DOWNLOAD_DIR})

                if not local_path:
                    continue

                existing_paths = [img["local_path"] for img in images_list]
                existing_paths.append(local_path)

                unique_paths = deduplicate_images.invoke({"image_paths": existing_paths})

                if local_path in unique_paths:
                    analysis = analyze_image.invoke({"image_path": local_path})

                    view_type = analysis.get("view", "unknown")
                    confidence = analysis.get("confidence", 0.0)
                    product_match = analysis.get("product_match", False)

                    if product_match:
                        images_list.append(
                            {
                                "url": img_url,
                                "local_path": local_path,
                                "view": view_type,
                                "confidence": confidence,
                            }
                        )

                        if view_type not in discovered_views:
                            discovered_views[view_type] = []
                        discovered_views[view_type].append(local_path)
                else:
                    self.logger.info("Skipped duplicate image: %s", local_path)

        tasks = self.remove_tasks_by_type(tasks, "find_images")
        return {"images": images_list, "discovered_views": discovered_views, "tasks": tasks}

    def collect_videos(self, state: dict) -> dict:
        """Search YouTube -> download -> extract frames -> classify views."""
        self.logger.info("Media agent: collecting videos")

        product = state.get("product", {})
        query = product.get("name", state.get("query", ""))
        missing_views = state.get("missing_views", REQUIRED_VIEWS.copy())

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
        all_frame_paths = []

        for video_info in selected_videos:
            url = video_info.get("url", "")
            self.logger.info("Processing video: %s", video_info.get("title", url))

            video_path = download_video.invoke({"url": url, "save_dir": VIDEO_DOWNLOAD_DIR})
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
            return {"tasks": tasks}

        self.logger.info("Deduplicating %d frames", len(all_frame_paths))
        unique_paths = deduplicate_images.invoke({"image_paths": all_frame_paths})
        self.logger.info("Kept %d unique frames after dedup", len(unique_paths))

        self.logger.info("Classifying view types for %d frames", len(unique_paths))
        for frame_path in unique_paths:
            analysis = analyze_image.invoke({"image_path": frame_path})

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

        if AI_FRAME_SELECTION and images_list:
            self.logger.info("Running AI frame selection")
            video_frame_paths = [
                img["local_path"] for img in images_list if img.get("source") == "video"
            ]
            selected = select_best_frames.invoke({
                "frame_paths": video_frame_paths,
                "views": missing_views,
                "max_per_view": 2,
            })

            video_frames: dict[str, list[str]] = {}
            for view, frames in selected.items():
                video_frames[view] = [f["path"] for f in frames if f.get("path")]

            tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
            return {
                "images": images_list,
                "discovered_views": discovered_views,
                "video_frames": video_frames,
                "tasks": tasks,
            }

        tasks = self.remove_tasks_by_type(state.get("tasks", []), "find_videos")
        return {"images": images_list, "discovered_views": discovered_views, "tasks": tasks}
