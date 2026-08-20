"""Video tools — download, extract frames, select best frames.

Provides LangChain tools:
  - download_video: download YouTube videos via yt-dlp with failure tracking
  - extract_frames: scene detection (PySceneDetect) + supplemental sampling
  - select_best_frames: AI-assisted frame selection using LLM Vision

All thresholds are configurable via settings:
  - VIDEO_SCENE_THRESHOLD (default 27.0): scene detection sensitivity
  - VIDEO_FRAME_JPEG_QUALITY (default 85): JPEG quality of extracted frames
  - VIDEO_MAX_FRAMES_PER_VIEW (default 2): max frames per view angle
  - VIDEO_AI_SELECTION_MAX_FRAMES (default 12): max frames for AI selection
  - VIDEO_FRAME_INTERVAL (default 5.0): supplemental sampling interval
  - VIDEO_MAX_RESOLUTION (default 480): max download resolution
  - VIDEO_MIN_DURATION (default 180): min video duration in seconds
  - VIDEO_MAX_DURATION (default 900): max video duration in seconds
"""

import base64
import json
import os

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from src.config import (
    AI_FRAME_SELECTION,
    REQUIRED_VIEWS,
    VIDEO_AI_SELECTION_MAX_FRAMES,
    VIDEO_DOWNLOAD_DIR,
    VIDEO_FRAME_INTERVAL,
    VIDEO_FRAME_JPEG_QUALITY,
    VIDEO_MAX_DURATION,
    VIDEO_MAX_FRAMES_PER_VIEW,
    VIDEO_MAX_RESOLUTION,
    VIDEO_MIN_DURATION,
    VIDEO_SCENE_THRESHOLD,
)
from src.config.logging import get_logger
from src.llm import get_vision_llm
from src.tools.logging import log_tool_call
from src.tools.utils.failed_urls import get_failed_url_tracker

logger = get_logger(__name__)


def is_video_url_failed(url: str) -> bool:
    """Check if a video URL has permanently failed."""
    return get_failed_url_tracker().is_failed(url)


def score_video(video: dict) -> float:
    """Score a video for quality/relevance. Higher is better."""
    title = video.get("title", "").lower()
    score = 0.5

    review_keywords = ["review", "unboxing", "hands on", "hands-on", "overview", "first look"]
    if any(kw in title for kw in review_keywords):
        score += 0.3

    duration = _parse_duration(video.get("duration", 0))
    if VIDEO_MIN_DURATION <= duration <= VIDEO_MAX_DURATION:
        score += 0.2
    elif (VIDEO_MIN_DURATION // 3) <= duration < VIDEO_MIN_DURATION:
        score += 0.1
    elif duration > VIDEO_MAX_DURATION * 2:
        score -= 0.2

    if 0 < duration < 60:
        score -= 0.3

    return score


def _parse_duration(duration) -> int:
    """Parse duration from string (e.g., '5:30', '1:23:45') or int to seconds."""
    if isinstance(duration, (int, float)):
        return int(duration)
    if not isinstance(duration, str):
        return 0

    parts = duration.strip().split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + int(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + int(s)
        else:
            return int(parts[0])
    except (ValueError, TypeError):
        return 0


@tool
@log_tool_call
def download_video(url: str, save_dir: str = VIDEO_DOWNLOAD_DIR, filename: str = "") -> str:
    """Download a YouTube video using yt-dlp.

    Downloads at capped resolution (default 720p) to save bandwidth.
    Returns the local file path, or empty string on failure.
    """
    tracker = get_failed_url_tracker()
    if tracker.is_failed(url):
        logger.debug("Skipping previously failed video URL: %s", url)
        return ""

    os.makedirs(save_dir, exist_ok=True)

    try:
        import yt_dlp

        if filename:
            # Use custom filename - strip extension if provided
            base_name = os.path.splitext(filename)[0]
            output_template = os.path.join(save_dir, f"{base_name}.%(ext)s")
        else:
            output_template = os.path.join(save_dir, "%(id)s.%(ext)s")

        format_str = (
            f"bestvideo[height<={VIDEO_MAX_RESOLUTION}]"
            f"+bestaudio/best[height<={VIDEO_MAX_RESOLUTION}]"
        )
        ydl_opts = {
            "format": format_str,
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "sleep_interval": 3,
            "max_sleep_interval": 10,
            "merge_output_format": "mp4",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                logger.error("Failed to extract info for %s", url)
                tracker.add(url)
                return ""
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                base = os.path.splitext(filename)[0]
                filename = base + ".mp4"

        if os.path.exists(filename):
            logger.info("Downloaded video: %s (%.1f MB)", filename, os.path.getsize(filename) / 1e6)
            return filename

        logger.error("Video file not found after download: %s", filename)
        tracker.add(url)
        return ""
    except ImportError:
        logger.error("yt-dlp not installed. Run: pip install yt-dlp")
        return ""
    except Exception as e:
        error_str = str(e).lower()
        if any(kw in error_str for kw in ("bot", "sign in", "confirm", "blocked", "captcha")):
            tracker.add(url)
            logger.warning("Permanently failed video URL (bot detection): %s", url)
        else:
            logger.error("Failed to download video %s: %s", url, e)
            tracker.add(url)
        return ""


@tool
@log_tool_call
def extract_frames(video_path: str, output_dir: str = "downloads/frames") -> list[str]:
    """Extract key frames from a video using scene detection + supplemental sampling.

    Uses PySceneDetect for scene changes, then adds uniform sampling within
    each scene to catch gradual product rotations.

    Returns list of extracted frame file paths.
    """
    os.makedirs(output_dir, exist_ok=True)

    try:
        import cv2
        import imagehash
        from PIL import Image as PILImage
        from scenedetect import ContentDetector, detect

        logger.info("Detecting scenes in: %s", video_path)
        scenes = detect(video_path, ContentDetector(threshold=VIDEO_SCENE_THRESHOLD))

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps <= 0 or total_frames <= 0:
            logger.error("Invalid video: fps=%s, frames=%s", fps, total_frames)
            cap.release()
            return []

        frame_paths = []
        extracted_hashes = set()

        def _extract_and_save(frame_num: int) -> str | None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if not ret:
                return None

            pil_img = PILImage.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            h = imagehash.phash(pil_img)
            h_str = str(h)
            if h_str in extracted_hashes:
                return None
            extracted_hashes.add(h_str)

            frame_path = os.path.join(output_dir, f"frame_{frame_num:06d}.jpg")
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, VIDEO_FRAME_JPEG_QUALITY])
            return frame_path

        logger.info("Found %d scenes, extracting frames", len(scenes))
        for start_time, end_time in scenes:
            start_frame = int(start_time.get_seconds() * fps)
            end_frame = int(end_time.get_seconds() * fps)
            mid_frame = (start_frame + end_frame) // 2

            path = _extract_and_save(mid_frame)
            if path:
                frame_paths.append(path)

            scene_duration_sec = end_time.get_seconds() - start_time.get_seconds()
            if scene_duration_sec > VIDEO_FRAME_INTERVAL * 2:
                interval_frames = int(VIDEO_FRAME_INTERVAL * fps)
                for f in range(start_frame + interval_frames, end_frame, interval_frames):
                    if f != mid_frame:
                        path = _extract_and_save(f)
                        if path:
                            frame_paths.append(path)

        cap.release()
        logger.info("Extracted %d unique frames from %s", len(frame_paths), video_path)
        return frame_paths

    except ImportError as e:
        logger.error("Missing dependency for frame extraction: %s", e)
        return []
    except Exception as e:
        logger.error("Frame extraction failed for %s: %s", video_path, e)
        return []


@tool
@log_tool_call
def select_best_frames(
    frame_paths: list[str], views: list[str], max_per_view: int = VIDEO_MAX_FRAMES_PER_VIEW
) -> dict[str, list[dict]]:
    """Use LLM Vision to select the best frames for each product view angle.

    Analyzes all extracted frames and picks the best ones per view category
    based on: product visibility, focus quality, angle clarity.

    Returns dict mapping view name to list of {path, confidence, reason}.
    """
    if not AI_FRAME_SELECTION or not frame_paths:
        return {
            v: [
                {"path": p, "confidence": 0.5, "reason": "no selection"}
                for p in frame_paths[:max_per_view]
            ]
            for v in views
        }

    try:
        llm = get_vision_llm()

        sample_frames = frame_paths[:VIDEO_AI_SELECTION_MAX_FRAMES]

        content_parts = []
        video_views = ", ".join(REQUIRED_VIEWS + ["bottom", "detail", "unknown"])
        content_parts.append({
            "type": "text",
            "text": (
                f"These are {len(sample_frames)} frames from product review "
                "videos.\n"
                "For each frame, determine:\n"
                f"1. Primary view angle: {video_views}\n"
                "2. Product visibility score (0.0-1.0)\n"
                "3. Image quality score (0.0-1.0)\n"
                "4. A brief reason for the rating\n\n"
                "View classification guide:\n"
                "- front, back, left, right, top, bottom: one angle\n"
                "- 360_strip: flipbook strip rotating through all angles\n"
                "- multi_angle_composite: grid combining multiple angles\n"
                "- detail: close-up of a specific feature\n"
                "- unknown: cannot determine a clear view\n\n"
                "Reply in this JSON format:\n"
                '{"frames": [{"index": 0, "view": "front", '
                '"product_vis": 0.9, "quality": 0.8, '
                '"reason": "..."}, ...]}'
            ),
        })

        for i, path in enumerate(sample_frames):
            if os.path.exists(path):
                with open(path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_data}"},
                })

        message = HumanMessage(content=content_parts)
        response = llm.invoke([message])
        from src.tools.usage import get_usage_tracker
        get_usage_tracker().record_llm(response)

        text = response.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        frame_analyses = data.get("frames", [])

        result: dict[str, list[dict]] = {v: [] for v in views}
        for analysis in frame_analyses:
            idx = analysis.get("index", 0)
            view = analysis.get("view", "unknown")
            if view not in result or len(result[view]) >= max_per_view:
                continue
            if idx < len(sample_frames):
                combined_score = (
                    analysis.get("product_vis", 0.5) * 0.6
                    + analysis.get("quality", 0.5) * 0.4
                )
                result[view].append({
                    "path": sample_frames[idx],
                    "confidence": combined_score,
                    "reason": analysis.get("reason", ""),
                })

        return result

    except Exception as e:
        logger.error("AI frame selection failed: %s", e)
        return {
            v: [
                {"path": p, "confidence": 0.5, "reason": "AI selection failed"}
                for p in frame_paths[:max_per_view]
            ]
            for v in views
        }
