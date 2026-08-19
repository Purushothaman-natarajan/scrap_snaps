"""Database persistence utilities for research results."""

from __future__ import annotations

from typing import Any

from src.config.logging import get_logger
from src.db import Claim, Image, Product, Source, Video, init_db

logger = get_logger(__name__)


def save_result_to_db(result: dict, database_url: str) -> int | None:
    """Save a research result to the database.

    Args:
        result: Dict with keys matching the Excel output format.
        database_url: SQLAlchemy database URL.

    Returns:
        Product ID if successful, None on failure.
    """
    session = init_db(database_url)

    try:
        product = Product(
            name=result.get("product_name", ""),
            query=result.get("product_name", ""),
            confidence=result.get("confidence", 0.0),
            status=result.get("status", "unknown"),
            row_index=result.get("row_index", 0),
        )
        session.add(product)
        session.flush()

        for url in result.get("source_urls", []):
            if url:
                source = Source(product_id=product.id, url=url, source_type="web")
                session.add(source)

        specs = result.get("specifications", {})
        if isinstance(specs, dict):
            for claim_type, value in specs.items():
                claim = Claim(
                    product_id=product.id,
                    claim_type=claim_type,
                    value=str(value),
                    confidence=0.8,
                )
                session.add(claim)

        image_urls = result.get("image_urls", [])
        image_paths = result.get("image_paths", [])
        image_views = result.get("image_views", [])
        for i, url in enumerate(image_urls):
            if url:
                img = Image(
                    product_id=product.id,
                    url=url,
                    local_path=image_paths[i] if i < len(image_paths) else "",
                    view=image_views[i] if i < len(image_views) else "unknown",
                    source="web",
                )
                session.add(img)

        video_urls = result.get("video_urls", [])
        video_paths = result.get("video_paths", [])
        for i, url in enumerate(video_urls):
            if url:
                vid = Video(
                    product_id=product.id,
                    url=url,
                    local_path=video_paths[i] if i < len(video_paths) else "",
                )
                session.add(vid)

        session.commit()
        logger.info("Saved result to DB: product_id=%d, name=%s", product.id, product.name)
        return product.id

    except Exception as e:
        session.rollback()
        logger.error("Failed to save result to DB: %s", e)
        return None
    finally:
        session.close()
