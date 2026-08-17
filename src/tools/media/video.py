"""Video tools - download, extract frames, select best frames."""

import base64
import json
import os

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from src.config import (
    AI_FRAME_SELECTION,
    VIDEO_DOWNLOAD_DIR,
    VIDEO_FRAME_INTERVAL,
    VIDEO_MAX_RESOLUTION,
)
from src.config.logging import get_logger
from src.llm import get_vision_llm
from src.tools.logging import log_tool_call

logger = get_logger(__name__)


def score_video(video: dict) -> float:
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


@tool
@log_tool_call
def download_video(url: str, save_dir: str = VIDEO_DOWNLOAD_DIR) -> str:
    """Download a YouTube video using yt-dlp.

    Downloads at capped resolution (default 720p) to save bandwidth.
    Returns the local file path, or empty string on failure.
    """
    os.makedirs(save_dir, exist_ok=True)

    try:
        import yt_dlp

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
                return ""
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                base = os.path.splitext(filename)[0]
                filename = base + ".mp4"

        if os.path.exists(filename):
            logger.info("Downloaded video: %s (%.1f MB)", filename, os.path.getsize(filename) / 1e6)
            return filename

        logger.error("Video file not found after download: %s", filename)
        return ""
    except ImportError:
        logger.error("yt-dlp not installed. Run: pip install yt-dlp")
        return ""
    except Exception as e:
        logger.error("Failed to download video %s: %s", url, e)
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
        scenes = detect(video_path, ContentDetector(threshold=27.0))

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
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
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
    frame_paths: list[str], views: list[str], max_per_view: int = 2
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

        sample_frames = frame_paths[:12]

        content_parts = []
        content_parts.append({
            "type": "text",
            "text": (
                f"These are {len(sample_frames)} frames from product review videos.\n"
                f"For each frame, determine:\n"
                f"1. Primary view angle: front, back, left, right, top, bottom, detail, unknown\n"
                f"2. Product visibility score (0.0-1.0): how clearly is the product shown?\n"
                f"3. Image quality score (0.0-1.0): focus, lighting, no obstructions?\n"
                f"4. A brief reason for the rating\n\n"
                f"Reply in this JSON format:\n"
                f'{{"frames": [{{"index": 0, "view": "front", "product_vis": 0.9, '
                f'"quality": 0.8, "reason": "..."}}, ...]}}'
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
