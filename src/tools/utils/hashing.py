"""Hashing utilities for image deduplication.

Provides perceptual hashing (pHash) for fuzzy image matching:
  - PHashCache: in-memory cache avoiding recomputation for known images
  - perceptual_hash(): compute pHash for an image file
  - are_hashes_similar(): compare two hashes with configurable Hamming distance
    (PHASH_SIMILARITY_THRESHOLD, default 10)
"""

import os
import time

import imagehash
from PIL import Image as PILImage

from src.config import PHASH_SIMILARITY_THRESHOLD
from src.config.logging import get_logger

logger = get_logger(__name__)


def perceptual_hash(image_path: str) -> str | None:
    """Compute perceptual hash (pHash) of an image.

    Returns string hash or None on error.
    """
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with PILImage.open(image_path) as img:
            img.load()
            # Convert to RGB for consistent hashing across modes
            if img.mode != "RGB":
                img = img.convert("RGB")
            return str(imagehash.phash(img))
    except Exception as e:
        logger.warning("Error computing pHash for %s: %s", image_path, e)
        return None


def are_similar(path1: str, path2: str, threshold: int = PHASH_SIMILARITY_THRESHOLD) -> bool:
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


def are_hashes_similar(
    hash1: str, hash2: str, threshold: int = PHASH_SIMILARITY_THRESHOLD
) -> bool:
    """Check if two pHash strings are within Hamming distance threshold."""
    if not hash1 or not hash2:
        return False
    return imagehash.hex_to_hash(hash1) - imagehash.hex_to_hash(hash2) <= threshold


class PHashCache:
    """Cache for perceptual hashes to avoid recomputing for known images.

    Maps image path -> (pHash, timestamp). Entries expire after TTL seconds.
    """

    def __init__(self, ttl: float = 3600.0) -> None:
        self._cache: dict[str, tuple[str, float]] = {}
        self._ttl = ttl

    def get(self, path: str) -> str | None:
        """Return cached pHash or None if not cached/expired."""
        if path in self._cache:
            h, ts = self._cache[path]
            if time.monotonic() - ts < self._ttl:
                return h
            del self._cache[path]
        return None

    def put(self, path: str, phash: str) -> None:
        """Store a pHash for the given path."""
        self._cache[path] = (phash, time.monotonic())

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


# Module-level singleton
_phash_cache = PHashCache()


def get_phash_cache() -> PHashCache:
    """Return the module-level pHash cache singleton."""
    return _phash_cache
