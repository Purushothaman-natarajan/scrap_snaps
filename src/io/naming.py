"""File naming conventions for downloads."""

from __future__ import annotations

import hashlib
import re


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    return text[:max_len].rstrip("_")


def _short_hash(text: str, length: int = 6) -> str:
    """Generate a short hash from text."""
    return hashlib.md5(text.encode()).hexdigest()[:length]


def make_filename(
    row_index: int,
    product_name: str,
    view: str,
    url: str,
    ext: str = "jpg",
) -> str:
    """Generate a standardized filename.

    Format: row_{ROW}_{product}_{view}_{hash}.{ext}
    """
    product_slug = _slugify(product_name)
    url_hash = _short_hash(url)
    return f"row_{row_index}_{product_slug}_{view}_{url_hash}.{ext}"


def make_image_path(
    row_index: int,
    product_name: str,
    view: str,
    url: str,
    base_dir: str = "downloads/images",
) -> str:
    """Generate full path for an image file."""
    filename = make_filename(row_index, product_name, view, url, ext="jpg")
    return f"{base_dir}/{filename}"


def make_video_path(
    row_index: int,
    product_name: str,
    url: str,
    base_dir: str = "downloads/videos",
) -> str:
    """Generate full path for a video file."""
    product_slug = _slugify(product_name)
    url_hash = _short_hash(url)
    filename = f"row_{row_index}_{product_slug}_{url_hash}.mp4"
    return f"{base_dir}/{filename}"
