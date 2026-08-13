"""Main entry point for the product research agent."""

import logging

from src.config import DATABASE_URL, MAX_ITERATIONS, RECURSION_LIMIT, REQUIRED_VIEWS, validate_env
from src.db import init_db
from src.graph import build_graph

logger = logging.getLogger(__name__)


def run_research(query: str):
    """Execute a research run for the given product query."""
    logger.info("Starting research for: %s", query)

    session = init_db(DATABASE_URL)
    logger.info("Database initialized at %s", DATABASE_URL)

    graph = build_graph()

    initial_state = {
        "query": query,
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
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    query = "Sony WH-1000XM5" if len(sys.argv) < 2 else sys.argv[1]

    validate_env()
    run_research(query)


if __name__ == "__main__":
    main()
