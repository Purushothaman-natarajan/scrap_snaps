"""Main entry point for the product research agent.

Single-query mode: runs the full research graph for one product query
and writes results to JSON + SQLite database.

Handles:
  - Focus area and media mode configuration
  - Recursion limit auto-scaling (max(RECURSION_LIMIT, MAX_ITERATIONS*8))
  - Usage tracking (tokens, LLM calls, SerpAPI calls, elapsed time)
  - Search cache clearing between runs
  - Result persistence to database (Product, Source, Claim, Image, Video, RunMetric)
  - JSON output with search cache stats and usage metrics
"""

import argparse
import json
import logging
import os
import re
import time

from src.config import (
    COLLECT_MEDIA,
    COLLECT_SPECS,
    DATABASE_URL,
    FOCUS_AREAS,
    MAX_ITERATIONS,
    RECURSION_LIMIT,
    validate_env,
)
from src.db.utils import save_result_to_db, save_run_metrics
from src.graph import build_graph
from src.pipeline.results import extract_result
from src.search.focus import get_focus_config
from src.state import create_initial_state
from src.tools.usage import get_usage_tracker
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

    tracker = get_usage_tracker()
    tracker.reset()
    tracker.start()

    focus_raw = focus_areas or FOCUS_AREAS
    focus = get_focus_config(focus_raw)
    if focus.areas:
        logger.info("Focus areas: %s", [a.value for a in focus.areas])

    specs = collect_specs if collect_specs is not None else COLLECT_SPECS
    media = collect_media if collect_media is not None else COLLECT_MEDIA
    if media == "none":
        media = None
    logger.info("Collect specs: %s, collect media: %s", specs, media)

    # Ensure recursion_limit is always sufficient for max_iterations.
    # Each cycle = planner + execute + verify + coverage = 4 nodes min.
    safe_recursion_limit = max(RECURSION_LIMIT, MAX_ITERATIONS * 8)
    logger.info(
        "Recursion limit: %d (max_iterations=%d)", safe_recursion_limit, MAX_ITERATIONS
    )

    graph = build_graph()

    initial_state = create_initial_state(
        query=query,
        focus_areas=[a.value for a in focus.areas],
        focus_config=focus.to_dict(),
        collect_specs=specs,
        collect_media=media,
        max_iterations=MAX_ITERATIONS,
    )

    logger.info("--- Execution Trace ---")
    final_state: dict = dict(initial_state)
    try:
        for event in graph.stream(initial_state, {"recursion_limit": safe_recursion_limit}):
            for key, value in event.items():
                out_summary = {}
                if value:
                    for k, v in value.items():
                        if isinstance(v, list):
                            out_summary[k] = f"list[{len(v)}]"
                        elif isinstance(v, dict):
                            out_summary[k] = f"dict[{len(v)} keys]" if len(v) > 2 else str(v)[:150]
                        else:
                            out_summary[k] = str(v)[:100]
                logger.info("Finished Node: %s -> %s", key, out_summary)
                if value:
                    final_state.update(value)
                # State snapshot after node
                logger.info(
                    "State: %d images, %d specs, %d views, missing %s, status=%s, budget=%s",
                    len(final_state.get("images", [])),
                    len(final_state.get("specifications", {})),
                    len(final_state.get("discovered_views", {})),
                    final_state.get("missing_views", [])[:3],
                    final_state.get("status", ""),
                    final_state.get("serpapi_budget_remaining", "?"),
                )
    except Exception as e:
        logger.exception("Graph stream failed: %s", e)
        final_state["status"] = "failed"
        final_state["error"] = str(e)

    logger.info("--- Research Complete ---")

    # Trace dump per run when LOG_CAPTURE enabled
    try:
        from src.config.settings import settings as _settings

        if _settings.log_capture:
            from pathlib import Path

            trace_dir = Path("logs/traces") / f"{_slugify(query)}_{int(time.time())}"
            trace_dir.mkdir(parents=True, exist_ok=True)
            (trace_dir / "final_state.json").write_text(json.dumps(final_state, indent=2, default=str), encoding="utf-8")
            logger.info("Trace dumped to %s", trace_dir)
    except Exception as e:
        logger.debug("Trace dump failed: %s", e)

    cache_stats = cache.stats
    logger.info(
        "Search cache stats: %d API calls, %d cache hits, %d cache misses",
        cache_stats["api_calls"],
        cache_stats["hits"],
        cache_stats["misses"],
    )

    usage_metrics = tracker.get_stats(search_cache_stats=cache_stats)

    # Build result — fallback only if graph truly produced no data
    _ok_statuses = ("done", "partial_complete", "complete", "max_iterations_reached")
    has_data = bool(
        final_state.get("images")
        or final_state.get("specifications")
        or final_state.get("status") in _ok_statuses
    )
    if has_data:
        result = extract_result(final_state, usage_metrics=usage_metrics)
    else:
        logger.warning("Graph produced no output — saving fallback result")
        result = {
            "query": query,
            "product_name": query,
            "status": "failed",
            "confidence": 0.0,
            "error": "Graph produced no output (recursion limit or crash)",
            "specifications": {},
            "source_urls": [],
            "image_urls": [],
            "image_paths": [],
            "image_views": [],
            "video_urls": [],
            "video_paths": [],
            "images": [],
            "videos": [],
            "required_views": [],
            "missing_views": [],
        }

    status = result.get("status", "unknown")
    is_failure = status in ("failed", "max_iterations_reached")
    is_partial = status == "partial_complete"

    # Save to database
    product_id = None
    try:
        product_id = save_result_to_db(result, DATABASE_URL)
        if product_id:
            save_run_metrics(product_id, usage_metrics, DATABASE_URL)
    except Exception as e:
        logger.warning("Failed to save result to DB: %s", e)

    # Save to JSON file
    try:
        result["search_cache_stats"] = cache_stats
        result["run_query"] = query

        if not output_path:
            slug = _slugify(query) or "unnamed_run"
            output_dir = "results"
            os.makedirs(output_dir, exist_ok=True)
            suffix = "_fallback" if is_failure else ""
            output_path = os.path.join(output_dir, f"{slug}{suffix}.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info("Results saved to %s", output_path)
    except Exception as e:
        logger.warning("Failed to save result to JSON: %s", e)

    logger.info(
        "Usage: %d input tokens, %d output tokens, %d LLM calls, %d SerpAPI calls",
        usage_metrics["input_tokens"],
        usage_metrics["output_tokens"],
        usage_metrics["llm_calls"],
        usage_metrics.get("serpapi_calls", 0),
    )

    images_count = len(result.get("images", []))
    videos_count = len(result.get("videos", []))
    specs_count = len(result.get("specifications", {}))
    sources_count = len(result.get("source_urls", []))

    header = "  RESEARCH FAILED" if is_failure else (
        "  RESEARCH PARTIAL" if is_partial else "  RESEARCH COMPLETE"
    )
    print("\n" + "=" * 60)
    print(header)
    print("=" * 60)
    print(f"  Query:      {query}")
    print(f"  Status:     {status}")
    print(f"  Confidence: {result.get('confidence', 0.0):.2f}")
    if is_failure:
        print(f"  Error:      {result.get('error', 'unknown')}")
    if is_partial:
        missing = result.get("missing_views", [])
        print(f"  Missing:    {', '.join(missing) if missing else 'none'}")
    print(f"  Images:     {images_count}")
    print(f"  Videos:     {videos_count}")
    print(f"  Specs:      {specs_count}")
    print(f"  Sources:    {sources_count}")
    in_tokens = usage_metrics["input_tokens"]
    out_tokens = usage_metrics["output_tokens"]
    print(f"  Tokens:     {in_tokens} in / {out_tokens} out")
    print(f"  LLM calls:  {usage_metrics['llm_calls']}")
    print(f"  SerpAPI:    {usage_metrics.get('serpapi_calls', 0)} calls")
    print(f"  Time:       {usage_metrics['elapsed_seconds']:.1f}s")
    print(f"  Output:     {output_path}")
    print(f"  DB ID:      {product_id or 'N/A'}")
    print("=" * 60)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Autonomous Product Research Agent",
        usage="%(prog)s <query> [--focus areas] [--collect-specs] [--collect-media mode]",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Sony WH-1000XM5",
        help='Product to research (default: "Sony WH-1000XM5")',
    )
    parser.add_argument(
        "--focus",
        help=(
            "Comma-separated focus areas "
            "(product_pages, seller_images, youtube, price_comparison, specs)"
        ),
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
        choices=[
            "images", "videos", "video_urls", "video_frames",
            "images_and_video_urls", "both", "none",
        ],
        default=None,
        help="What media to collect: images, videos, both (default), or none",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file path (default: results/<query>.json)",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Run with fast demo settings (images only, no specs, 10 iterations)",
    )

    args = parser.parse_args()

    # Apply --example overrides
    if args.example:
        args.focus = "product_pages,youtube"
        args.collect_media = "images"
        args.collect_specs = False

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
