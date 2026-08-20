"""Database persistence utilities for research results.

Provides:
  - ``save_result_to_db()`` — saves a research result dict to Product, Source,
    Claim, Image, Video tables. Accepts an existing session or creates one.
  - ``save_run_metrics()`` — saves usage metrics (tokens, API calls, timing)
    to the RunMetric table linked to a Product.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.config.logging import get_logger
from src.db import Claim, Image, Product, RunMetric, Source, Video, init_db

logger = get_logger(__name__)


def save_result_to_db(
    result: dict,
    database_url: str | None = None,
    session: Session | None = None,
) -> int | None:
    """Save a research result to the database.

    Args:
        result: Dict with keys matching the Excel output format.
        database_url: SQLAlchemy database URL. Ignored if session is provided.
        session: An existing SQLAlchemy Session.

    Returns:
        Product ID if successful, None on failure.
    """
    if session is None:
        if database_url is None:
            raise ValueError("Either session or database_url must be provided")
        session_to_use = init_db(database_url)
        close_session = True
    else:
        session_to_use = session
        close_session = False

    try:
        product = Product(
            name=result.get("product_name", ""),
            query=result.get("product_name", ""),
            confidence=result.get("confidence", 0.0),
            status=result.get("status", "unknown"),
            row_index=result.get("row_index", 0),
        )
        session_to_use.add(product)
        session_to_use.flush()

        for url in result.get("source_urls", []):
            if url:
                source = Source(product_id=product.id, url=url, source_type="web")
                session_to_use.add(source)

        specs = result.get("specifications", {})
        if isinstance(specs, dict):
            for claim_type, value in specs.items():
                claim = Claim(
                    product_id=product.id,
                    claim_type=claim_type,
                    value=str(value),
                    confidence=0.8,
                )
                session_to_use.add(claim)

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
                session_to_use.add(img)

        video_urls = result.get("video_urls", [])
        video_paths = result.get("video_paths", [])
        for i, url in enumerate(video_urls):
            if url:
                vid = Video(
                    product_id=product.id,
                    url=url,
                    local_path=video_paths[i] if i < len(video_paths) else "",
                )
                session_to_use.add(vid)

        session_to_use.commit()
        logger.info("Saved result to DB: product_id=%d, name=%s", product.id, product.name)
        return product.id

    except Exception as e:
        session_to_use.rollback()
        logger.error("Failed to save result to DB: %s", e)
        return None
    finally:
        if close_session:
            session_to_use.close()


def save_run_metrics(
    product_id: int,
    metrics: dict,
    database_url: str | None = None,
    session: Session | None = None,
) -> None:
    """Save usage metrics for a research run.

    Args:
        product_id: The Product ID to link metrics to.
        metrics: Dict with keys like input_tokens, output_tokens, etc.
        database_url: SQLAlchemy database URL. Ignored if session is provided.
        session: An existing SQLAlchemy Session.
    """
    if session is None:
        if database_url is None:
            raise ValueError("Either session or database_url must be provided")
        session_to_use = init_db(database_url)
        close_session = True
    else:
        session_to_use = session
        close_session = False

    try:
        run_metric = RunMetric(
            product_id=product_id,
            input_tokens=metrics.get("input_tokens", 0),
            output_tokens=metrics.get("output_tokens", 0),
            total_tokens=metrics.get("total_tokens", 0),
            llm_calls=metrics.get("llm_calls", 0),
            serpapi_calls=metrics.get("serpapi_calls", 0),
            serpapi_hits=metrics.get("serpapi_hits", 0),
            serpapi_misses=metrics.get("serpapi_misses", 0),
            elapsed_seconds=metrics.get("elapsed_seconds", 0.0),
        )
        session_to_use.add(run_metric)
        session_to_use.commit()
        logger.info("Saved run metrics: product_id=%d", product_id)
    except Exception as e:
        session_to_use.rollback()
        logger.error("Failed to save run metrics: %s", e)
    finally:
        if close_session:
            session_to_use.close()
