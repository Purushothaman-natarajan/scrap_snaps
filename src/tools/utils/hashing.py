"""Hashing utilities for image deduplication."""

import os

import imagehash
from PIL import Image as PILImage

from src.config.logging import get_logger

logger = get_logger(__name__)


def perceptual_hash(image_path: str) -> str | None:
    """Compute perceptual hash (pHash) of an image.

    Returns string hash or None on error.
    """
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        img = PILImage.open(image_path)
        return str(imagehash.phash(img))
    except Exception as e:
        logger.warning("Error computing pHash for %s: %s", image_path, e)
        return None


def are_similar(path1: str, path2: str, threshold: int = 10) -> bool:
    """Check if two images are perceptually similar.

    Args:
        path1: First image path.
        path2: Second image path.
        threshold: Maximum Hamming distance to consider images similar.
    """
    h1 = perceptual_hash(path1)
    h2 = perceptual_hash(path2)
    if h1 is None or h2 is None:
        return False
    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2) <= threshold
