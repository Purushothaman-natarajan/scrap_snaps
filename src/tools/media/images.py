"""Image tools — download, analyze, deduplicate.

Provides LangChain tools:
  - download_image: download with failure tracking (bot/403 detection)
  - analyze_image: classify product image view type using LLM Vision
  - analyze_images_batch: batch analyze up to IMAGE_BATCH_SIZE images per call
  - deduplicate_images: fuzzy pHash matching with configurable threshold

Features:
  - pHash-based analysis cache (IMAGE_ANALYZE_CACHE_TTL, default 1h) avoids
    re-analyzing the same image across cycles
  - Dynamic view types from REQUIRED_VIEWS setting (supports custom views)
  - Configurable IMAGE_BATCH_SIZE (default 5) for cost/quality trade-off
  - Failed URL tracking via shared FailedURLTracker singleton
"""

import base64
import hashlib
import json
import os
import time
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from src.config import (
    DOWNLOAD_DIR,
    IMAGE_ANALYZE_CACHE_TTL,
    IMAGE_BATCH_SIZE,
    MAX_DOWNLOAD_SIZE,
    REQUIRED_VIEWS,
)
from src.config.logging import get_logger
from src.llm import get_vision_llm
from src.tools.logging import log_tool_call
from src.tools.utils.failed_urls import get_failed_url_tracker
from src.tools.utils.hashing import (
    PHashCache,
    are_hashes_similar,
    get_phash_cache,
    perceptual_hash,
)
from src.tools.utils.http import http_get

logger = get_logger(__name__)

# Module-level cache for analyze_image results, keyed by pHash.
# Avoids re-analyzing the same image in different cycles.
_analyze_cache: dict[str, dict[str, Any]] = {}
_analyze_cache_timestamps: dict[str, float] = {}


def _get_analyze_cache(phash: str) -> dict[str, Any] | None:
    """Get cached analysis result by pHash, if not expired."""
    if phash in _analyze_cache:
        ts = _analyze_cache_timestamps.get(phash, 0)
        if time.monotonic() - ts < IMAGE_ANALYZE_CACHE_TTL:
            return _analyze_cache[phash]
        del _analyze_cache[phash]
        _analyze_cache_timestamps.pop(phash, None)
    return None


def _put_analyze_cache(phash: str, result: dict[str, Any]) -> None:
    """Store analysis result in cache."""
    _analyze_cache[phash] = result
    _analyze_cache_timestamps[phash] = time.monotonic()


def is_image_url_failed(url: str) -> bool:
    """Check if an image URL has permanently failed."""
    return get_failed_url_tracker().is_failed(url)


def get_failed_image_urls() -> set[str]:
    """Return the shared failed image URLs set."""
    return get_failed_url_tracker().get_all()


@tool
@log_tool_call
def download_image(url: str, save_dir: str = DOWNLOAD_DIR, filename: str = "") -> str:
    """Download an image from a URL and return its local path."""
    tracker = get_failed_url_tracker()
    if tracker.is_failed(url):
        logger.debug("Skipping previously failed image URL: %s", url)
        return ""

    os.makedirs(save_dir, exist_ok=True)

    if filename:
        local_path = os.path.join(save_dir, filename)
    else:
        filename_from_url = url.split("/")[-1].split("?")[0]
        if not filename_from_url or "." not in filename_from_url:
            ext = ".jpg"
            filename_from_url = f"image_{hashlib.md5(url.encode()).hexdigest()}{ext}"
        local_path = os.path.join(save_dir, filename_from_url)

    if os.path.exists(local_path):
        return local_path

    try:
        response = http_get(url)

        content_length = int(response.headers.get("content-length", "0"))
        if content_length > MAX_DOWNLOAD_SIZE:
            logger.warning("Image too large (%d bytes): %s", content_length, url)
            return ""

        content_type = response.headers.get("content-type", "")
        if "image" not in content_type and not url.lower().endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".webp")
        ):
            logger.warning(
                "URL does not appear to be an image: %s (content-type: %s)", url, content_type
            )

        with open(local_path, "wb") as f:
            f.write(response.content)
        return local_path
    except Exception as e:
        error_str = str(e).lower()
        if any(kw in error_str for kw in ("403", "forbidden", "bot", "captcha", "sign in")):
            tracker.add(url)
            logger.warning("Permanently failed image URL (bot protection): %s", url)
        else:
            logger.error("Error downloading %s: %s", url, e)
        return ""


def _parse_analysis_text(text: str) -> dict[str, Any] | None:
    """Parse LLM JSON text into an analysis dict. Returns None on failure."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    data = json.loads(text)
    required_keys = {"product_match", "view", "confidence"}
    if required_keys.issubset(data.keys()):
        return data
    return None


@tool
@log_tool_call
def analyze_image(image_path: str) -> dict:
    """Analyze an image using a vision model to determine the view type.

    Results are cached by pHash to avoid re-analyzing the same image.
    """
    if not os.path.exists(image_path):
        return {"product_match": False, "view": "unknown", "confidence": 0.0}

    phash = perceptual_hash(image_path)
    if phash:
        cached = _get_analyze_cache(phash)
        if cached is not None:
            logger.debug("analyze_image cache hit for %s", os.path.basename(image_path))
            return cached

    try:
        llm = get_vision_llm()

        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        view_options = ", ".join(REQUIRED_VIEWS)
        prompt = (
            "Analyze this product image. Determine the primary view of the product "
            f"from this list: [{view_options}]. "
            "Is it clearly a product image (not a person or generic scene)?\n\n"
            "Reply strictly in this JSON format:\n"
            '{"product_match": true/false, "view": "one_of_the_options", '
            '"confidence": 0.0_to_1.0}'
        )

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
            ]
        )

        response = llm.invoke([message])
        from src.tools.usage import get_usage_tracker
        get_usage_tracker().record_llm(response)
        data = _parse_analysis_text(response.content.strip())

        if data is None:
            logger.warning("LLM response missing required keys for %s", image_path)
            data = {"product_match": False, "view": "unknown", "confidence": 0.0}

        if phash:
            _put_analyze_cache(phash, data)

        return data
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON response for %s: %s", image_path, e)
        return {"product_match": False, "view": "unknown", "confidence": 0.0}
    except Exception as e:
        logger.error("Error analyzing image %s: %s", image_path, e)
        return {"product_match": False, "view": "unknown", "confidence": 0.0}


@tool
@log_tool_call
def analyze_images_batch(image_paths: list[str]) -> list[dict]:
    """Analyze multiple images in a single LLM call (cost-optimized).

    Sends up to 5 images per call. Returns a list of analysis results
    in the same order as the input paths. Images that fail to load
    get a default "unknown" result.

    This is 4-5x cheaper than calling analyze_image individually.
    """
    if not image_paths:
        return []

    batch = image_paths[:IMAGE_BATCH_SIZE]
    if len(image_paths) > IMAGE_BATCH_SIZE:
        logger.warning(
            "Batch limited to %d images, %d provided — %d will be skipped",
            IMAGE_BATCH_SIZE,
            len(image_paths),
            len(image_paths) - IMAGE_BATCH_SIZE,
        )
    results: list[dict | None] = [None] * len(batch)

    uncached_indices: list[int] = []
    uncached_paths: list[tuple[str, str | None]] = []

    for i, path in enumerate(batch):
        if not path or not os.path.exists(path):
            results[i] = {"product_match": False, "view": "unknown", "confidence": 0.0}
            continue

        phash = perceptual_hash(path)
        if phash:
            cached = _get_analyze_cache(phash)
            if cached is not None:
                results[i] = cached
                continue

        uncached_indices.append(i)
        uncached_paths.append((path, phash))

    if not uncached_paths:
        return [r for r in results]  # type: ignore

    try:
        llm = get_vision_llm()

        view_options = ", ".join(REQUIRED_VIEWS)
        content_parts: list[dict] = []
        content_parts.append({
            "type": "text",
            "text": (
                f"Analyze these {len(uncached_paths)} product images.\n"
                "For each image, determine:\n"
                "1. Is it a product image (not a person or generic scene)?\n"
                f"2. Primary view angle: {view_options}\n"
                "3. Confidence (0.0-1.0)\n\n"
                "Reply in this JSON format:\n"
                '{"results": [{"index": 0, "product_match": true/false, '
                '"view": "one_of_options", "confidence": 0.0_to_1.0}, ...]}'
            ),
        })

        for path, _ in uncached_paths:
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

        parsed = json.loads(text)
        batch_results = parsed.get("results", [])

        for j, idx in enumerate(uncached_indices):
            if j < len(batch_results):
                result = batch_results[j]
                required_keys = {"product_match", "view", "confidence"}
                if required_keys.issubset(result.keys()):
                    results[idx] = result
                    _, phash = uncached_paths[j]
                    if phash:
                        _put_analyze_cache(phash, result)
                else:
                    results[idx] = {"product_match": False, "view": "unknown", "confidence": 0.0}
            else:
                results[idx] = {"product_match": False, "view": "unknown", "confidence": 0.0}

        return [r for r in results]  # type: ignore

    except Exception as e:
        logger.error("Batch image analysis failed: %s", e)
        for idx in uncached_indices:
            if results[idx] is None:
                results[idx] = {"product_match": False, "view": "unknown", "confidence": 0.0}
        return [r for r in results]  # type: ignore


@tool
@log_tool_call
def deduplicate_images(
    image_paths: list[str],
    threshold: int = 10,
    cache: PHashCache | None = None,
) -> list[str]:
    """Take a list of image paths and return paths of unique images.

    Uses fuzzy pHash matching with configurable Hamming distance threshold.
    Images within the threshold are considered duplicates.

    Args:
        image_paths: List of image file paths to deduplicate.
        threshold: Max Hamming distance to consider images similar (default: 10).
        cache: Optional PHashCache to avoid recomputing hashes for known images.
    """
    if cache is None:
        cache = get_phash_cache()

    unique_paths: list[str] = []
    seen_hashes: list[str] = []

    for path in image_paths:
        if not path or not os.path.exists(path):
            continue

        h = cache.get(path)
        if h is None:
            h = perceptual_hash(path)
            if h is not None:
                cache.put(path, h)

        if h is None:
            continue

        is_dup = False
        for seen_h in seen_hashes:
            if are_hashes_similar(h, seen_h, threshold):
                is_dup = True
                break

        if not is_dup:
            seen_hashes.append(h)
            unique_paths.append(path)

    return unique_paths
