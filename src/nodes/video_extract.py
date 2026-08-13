"""Video extraction node - find, download, and extract product images from YouTube videos."""

from __future__ import annotations

import logging
import os

from src.config import (
    AI_FRAME_SELECTION,
    DOWNLOAD_DIR,
    MAX_VIDEO_RESULTS,
    REQUIRED_VIEWS,
    VIDEO_DOWNLOAD_DIR,
)
from src.state import ResearchState
from src.tools import (
    analyze_image,
    deduplicate_images,
    download_video,
    extract_frames,
    search_videos,
    select_best_frames,
)

logger = logging.getLogger(__name__)


def _score_video(video: dict) -> float:
    """Score a video for quality/relevance. Higher is better."""
    title = video.get("title", "").lower()
    score = 0.5

    review_keywords = ["review", "unboxing", "hands on", "hands-on", "overview", "first look"]
    if any(kw in title for kw in review_keywords):
        score += 0.3

    duration = video.get("duration", 0)
    if 180 <= duration <= 900:
        score += 0.2
    elif 60 <= duration < 180:
        score += 0.1
    elif duration > 1800:
        score -= 0.2

    if 0 < duration < 60:
        score -= 0.3

    return score


def video_extract(state: ResearchState) -> dict:
    """Video extraction node.

    Searches YouTube for product videos, downloads the best ones,
    extracts key frames via scene detection, and classifies views.
    """
    logger.info("Video extract node executing")

    product = state.get("product", {})
    query = product.get("name", state.get("query", ""))
    missing_views = state.get("missing_views", REQUIRED_VIEWS.copy())

    # Step 1: Search for YouTube videos
    search_q = f"{query} review angles"
    videos = search_videos.invoke({"query": search_q, "limit": 10})

    if not videos:
        logger.warning("No videos found for query: %s", query)
        tasks = [t for t in state.get("tasks", []) if t.get("type") != "find_videos"]
        return {"tasks": tasks}

    # Step 2: Score and rank videos
    for v in videos:
        v["score"] = _score_video(v)
    videos.sort(key=lambda v: v.get("score", 0), reverse=True)

    # Step 3: Select top N videos (configurable)
    selected_videos = videos[:MAX_VIDEO_RESULTS]
    logger.info("Selected %d videos for processing", len(selected_videos))

    # Step 4: Process each video
    images_list = state.get("images", [])
    discovered_views = state.get("discovered_views", {})
    all_frame_paths = []

    for video_info in selected_videos:
        url = video_info.get("url", "")
        logger.info("Processing video: %s", video_info.get("title", url))

        # Download video
        video_path = download_video.invoke({"url": url, "save_dir": VIDEO_DOWNLOAD_DIR})
        if not video_path:
            logger.warning("Failed to download video: %s", url)
            continue

        # Extract frames
        video_name = os.path.basename(video_path).split(".")[0]
        frames_dir = os.path.join(DOWNLOAD_DIR, "frames", video_name)
        frame_paths = extract_frames.invoke({"video_path": video_path, "output_dir": frames_dir})
        all_frame_paths.extend(frame_paths)

        # Clean up: delete the video file to free disk space
        try:
            os.remove(video_path)
            logger.info("Deleted video file: %s", video_path)
        except OSError as e:
            logger.warning("Failed to delete video %s: %s", video_path, e)

    if not all_frame_paths:
        logger.warning("No frames extracted from any video")
        tasks = [t for t in state.get("tasks", []) if t.get("type") != "find_videos"]
        return {"tasks": tasks}

    # Step 5: Deduplicate frames across all videos
    logger.info("Deduplicating %d frames", len(all_frame_paths))
    unique_paths = deduplicate_images.invoke({"image_paths": all_frame_paths})
    logger.info("Kept %d unique frames after dedup", len(unique_paths))

    # Step 6: Classify each frame's view type
    logger.info("Classifying view types for %d frames", len(unique_paths))
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

    # Step 7: AI frame selection (if enabled)
    if AI_FRAME_SELECTION and images_list:
        logger.info("Running AI frame selection")
        video_frame_paths = [
            img["local_path"] for img in images_list if img.get("source") == "video"
        ]
        selected = select_best_frames.invoke({
            "frame_paths": video_frame_paths,
            "views": missing_views,
            "max_per_view": 2,
        })

        # Build video_frames dict from AI selection
        video_frames: dict[str, list[str]] = {}
        for view, frames in selected.items():
            video_frames[view] = [f["path"] for f in frames if f.get("path")]

        tasks = [t for t in state.get("tasks", []) if t.get("type") != "find_videos"]
        return {
            "images": images_list,
            "discovered_views": discovered_views,
            "video_frames": video_frames,
            "tasks": tasks,
        }

    tasks = [t for t in state.get("tasks", []) if t.get("type") != "find_videos"]
    return {"images": images_list, "discovered_views": discovered_views, "tasks": tasks}
