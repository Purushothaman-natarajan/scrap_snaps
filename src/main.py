"""Main entry point for the product research agent."""

import argparse
import json
import logging
import os
import re

from src.config import (
    COLLECT_MEDIA,
    COLLECT_SPECS,
    DATABASE_URL,
    FOCUS_AREAS,
    MAX_ITERATIONS,
    RECURSION_LIMIT,
    REQUIRED_VIEWS,
    validate_env,
)
from src.db import init_db
from src.graph import build_graph
from src.search.focus import get_focus_config
from src.tools.web.cache import get_search_cache

logger = logging.getLogger(__name__)


def _slugify(text: str, max_len: int = 50) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    return text[:max_len].rstrip("_")


def run_research(
    query: str,
    focus_areas: str | None = None,
    collect_specs: bool | None = None,
    collect_media: str | None = None,
    output_path: str | None = None,
):
    """Execute a research run for the given product query."""
    logger.info("Starting research for: %s", query)

    # Clear search cache for this run
    cache = get_search_cache()
    cache.clear()

    focus_raw = focus_areas or FOCUS_AREAS
    focus = get_focus_config(focus_raw)
    if focus.areas:
        logger.info("Focus areas: %s", [a.value for a in focus.areas])

    specs = collect_specs if collect_specs is not None else COLLECT_SPECS
    media = collect_media if collect_media is not None else COLLECT_MEDIA
    logger.info("Collect specs: %s, collect media: %s", specs, media)

    session = init_db(DATABASE_URL)
    logger.info("Database initialized at %s", DATABASE_URL)

    graph = build_graph()

    initial_state = {
        "query": query,
        "focus_areas": [a.value for a in focus.areas],
        "focus_config": focus.to_dict(),
        "collect_specs": specs,
        "collect_media": media,
        "product": {},
        "candidates": [],
        "search_queries": [],
        "searched_queries": [],
        "sources": [],
        "evidence": [],
        "specifications": {},
        "images": [],
        "videos": [],
        "required_views": REQUIRED_VIEWS,
        "discovered_views": {},
        "missing_views": REQUIRED_VIEWS.copy(),
        "tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "failed_media_urls": [],
        "previous_task_fingerprints": [],
        "iterations": 0,
        "max_iterations": MAX_ITERATIONS,
        "confidence": 0.0,
        "status": "started",
    }

    logger.info("--- Execution Trace ---")
    final_state = None
    for event in graph.stream(initial_state, {"recursion_limit": RECURSION_LIMIT}):
        for key, value in event.items():
            logger.info("Finished Node: %s", key)
            final_state = value

    logger.info("--- Research Complete ---")

    # Log search cache stats
    cache_stats = cache.stats
    logger.info(
        "Search cache stats: %d API calls, %d cache hits, %d cache misses",
        cache_stats["api_calls"],
        cache_stats["hits"],
        cache_stats["misses"],
    )

    if final_state:
        # Save to database
        try:
            from src.db.utils import save_result_to_db
            from src.pipeline.results import extract_result
            result = extract_result(final_state)
            save_result_to_db(result, DATABASE_URL)
        except Exception as e:
            logger.warning("Failed to save result to DB: %s", e)

        # Save to JSON file
        try:
            from src.pipeline.results import extract_result
            result = extract_result(final_state)
            result["search_cache_stats"] = cache_stats
            result["run_query"] = query

            if not output_path:
                slug = _slugify(query)
                output_dir = "results"
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"{slug}.json")

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=str)
            logger.info("Results saved to %s", output_path)
        except Exception as e:
            logger.warning("Failed to save result to JSON: %s", e)

    session.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Autonomous Product Research Agent",
        usage="%(prog)s <query> [--focus areas] [--collect-specs] [--collect-media mode]",
    )
    parser.add_argument(
        "query",
        help='Product to research (e.g. "Sony WH-1000XM5")',
    )
    parser.add_argument(
        "--focus",
        help="Comma-separated focus areas (product_pages, seller_images, youtube, price_comparison, specs)",
        default=None,
    )
    parser.add_argument(
        "--collect-specs",
        action="store_true",
        default=None,
        help="Collect specifications (enabled by default)",
    )
    parser.add_argument(
        "--no-collect-specs",
        dest="collect_specs",
        action="store_false",
        help="Disable specification collection",
    )
    parser.add_argument(
        "--collect-media",
        choices=["images", "videos", "both", "none"],
        default=None,
        help="What media to collect: images, videos, both (default), or none",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file path (default: results/<query>.json)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    validate_env()
    run_research(
        args.query,
        focus_areas=args.focus,
        collect_specs=args.collect_specs,
        collect_media=args.collect_media,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
