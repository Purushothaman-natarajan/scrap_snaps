"""Main entry point for the product research agent."""

import argparse
import logging

from src.config import (
    COLLECT,
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

logger = logging.getLogger(__name__)


def run_research(query: str, focus_areas: str | None = None, collect: str | None = None):
    """Execute a research run for the given product query."""
    logger.info("Starting research for: %s", query)

    # Use CLI focus if provided, otherwise fall back to config
    focus_raw = focus_areas or FOCUS_AREAS
    focus = get_focus_config(focus_raw)
    if focus.areas:
        logger.info("Focus areas: %s", [a.value for a in focus.areas])

    # Use CLI collect if provided, otherwise fall back to config
    collect_mode = collect or COLLECT
    logger.info("Collect mode: %s", collect_mode)

    session = init_db(DATABASE_URL)
    logger.info("Database initialized at %s", DATABASE_URL)

    graph = build_graph()

    initial_state = {
        "query": query,
        "focus_areas": [a.value for a in focus.areas],
        "focus_config": focus.to_dict(),
        "collect": collect_mode,
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
        "iterations": 0,
        "max_iterations": MAX_ITERATIONS,
        "confidence": 0.0,
        "status": "started",
    }

    logger.info("--- Execution Trace ---")
    for event in graph.stream(initial_state, {"recursion_limit": RECURSION_LIMIT}):
        for key, value in event.items():
            logger.info("Finished Node: %s", key)

    logger.info("--- Research Complete ---")
    session.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Autonomous Product Research Agent",
        usage="%(prog)s <query> [--focus areas] [--collect mode]",
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
        "--collect",
        choices=["specs", "images", "both"],
        help="What to collect: specs (text only), images (images only), or both (default)",
        default=None,
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    validate_env()
    run_research(args.query, focus_areas=args.focus, collect=args.collect)


if __name__ == "__main__":
    main()
