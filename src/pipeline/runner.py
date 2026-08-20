"""Pipeline runner — batch orchestrator for processing Excel rows.

PipelineRunner processes an Excel file row by row through the research graph.
Features:
  - Shared DB engine created once per pipeline run (fewer connections)
  - Per-row usage tracking (tokens, LLM calls, SerpAPI calls, elapsed time)
  - Search cache cleared and usage tracker reset between rows
  - Checkpoint-based crash recovery (skip processed rows on restart)
  - Streaming Excel I/O for large files
  - Results written to both Excel and database per row
  - Pipeline config loaded from config.yaml (``pipeline:`` section)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src.config import DATABASE_URL, RECURSION_LIMIT
from src.config.yaml_loader import DEFAULT_CONFIG_PATH, get_pipeline_config
from src.db import get_engine, get_session
from src.db.utils import save_result_to_db, save_run_metrics
from src.graph import build_graph
from src.io import get_storage, read_excel_rows, write_row_result
from src.pipeline.checkpoint import CheckpointData, CheckpointManager
from src.pipeline.results import extract_result_for_row
from src.search.focus import get_focus_config
from src.state import create_initial_state
from src.tools.usage import get_usage_tracker
from src.tools.web.cache import get_search_cache

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""

    input_file: str
    output_file: str = ""
    sheet: str | None = None
    header_row: int = 1
    batch_size: int = 10
    collect_specs: bool = True
    collect_media: str = "images_and_video_urls"
    focus_areas: str = ""
    max_iterations: int = 30
    storage_backend: str = "local"
    storage_base_dir: str = "downloads"
    skip_existing: bool = True

    @classmethod
    def from_json(cls, path: str) -> PipelineConfig:
        """Load config from JSON file (legacy, kept for backward compat)."""
        with open(path) as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_yaml(cls, path: str = DEFAULT_CONFIG_PATH) -> PipelineConfig:
        """Load pipeline config from the ``pipeline:`` section of config.yaml."""
        data = get_pipeline_config(path)
        if not data:
            raise FileNotFoundError(f"No pipeline config found in {path}")
        # Filter to known fields
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered)

    @classmethod
    def load(cls, path: str | None = None) -> PipelineConfig:
        """Load config from YAML (default) or JSON (if path ends with .json)."""
        if path and path.endswith(".json"):
            return cls.from_json(path)
        return cls.from_yaml(path or DEFAULT_CONFIG_PATH)

    def to_json(self, path: str) -> None:
        """Save config to JSON file."""
        with open(path, "w") as f:
            json.dump(self.__dict__, f, indent=2)


class PipelineRunner:
    """Batch orchestrator for processing Excel files row by row."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.checkpoint_mgr = CheckpointManager()
        self.storage = get_storage(
            config.storage_backend,
            base_dir=config.storage_base_dir,
        )

    def run(self) -> dict:
        """Execute the pipeline over all rows.

        Returns:
            Summary dict with totals.
        """
        config = self.config
        if not config.output_file:
            base = Path(config.input_file).stem
            config.output_file = f"results_{base}.xlsx"

        checkpoint = self.checkpoint_mgr.load(config.input_file)
        if checkpoint is None:
            checkpoint = CheckpointData(
                input_file=config.input_file,
                output_file=config.output_file,
                batch_size=config.batch_size,
                started_at=time.time(),
            )

        checkpoint.total_rows = self._estimate_rows(config)
        logger.info(
            "Pipeline starting: %s rows, batch_size=%d",
            checkpoint.total_rows,
            config.batch_size,
        )

        summary = {
            "total": checkpoint.total_rows,
            "processed": 0,
            "failed": 0,
            "skipped": 0,
        }

        # Create shared DB engine once for all rows
        db_engine = get_engine(DATABASE_URL)

        for batch in read_excel_rows(
            config.input_file,
            sheet=config.sheet,
            header_row=config.header_row,
            batch_size=config.batch_size,
        ):
            for row_data in batch:
                row_idx = row_data.get("__row_index", 0)

                if config.skip_existing and self.checkpoint_mgr.is_processed(checkpoint, row_idx):
                    summary["skipped"] += 1
                    continue

                # Clear per-row singletons to avoid cross-product contamination
                get_search_cache().clear()
                from src.tools.media.images import _analyze_cache, _analyze_cache_timestamps
                from src.tools.utils.failed_urls import get_failed_url_tracker
                from src.tools.utils.hashing import get_phash_cache

                get_failed_url_tracker().clear()
                get_phash_cache().clear()
                _analyze_cache.clear()
                _analyze_cache_timestamps.clear()
                tracker = get_usage_tracker()
                tracker.reset()
                tracker.start()

                try:
                    result = self._process_row(row_data, config, db_engine=db_engine)

                    cache_stats = get_search_cache().stats
                    usage_metrics = tracker.get_stats(search_cache_stats=cache_stats)
                    result["usage_metrics"] = usage_metrics
                    # Flatten metrics into result for Excel column mapping
                    for k, v in usage_metrics.items():
                        result[k] = v

                    write_row_result(config.output_file, result)

                    # Save to database using a row-specific session
                    session = None
                    try:
                        session = get_session(db_engine)
                        product_id = save_result_to_db(result, session=session)
                        if product_id:
                            save_run_metrics(product_id, usage_metrics, session=session)
                        session.commit()
                    except Exception as db_err:
                        logger.warning("Failed to save to DB for row %d: %s", row_idx, db_err)
                        if session is not None:
                            try:
                                session.rollback()
                            except Exception:
                                pass
                    finally:
                        if session is not None:
                            try:
                                session.close()
                            except Exception:
                                pass

                    self.checkpoint_mgr.mark_completed(checkpoint, row_idx)
                    summary["processed"] += 1
                    logger.info(
                        "Row %d done (%d/%d)",
                        row_idx,
                        summary["processed"],
                        checkpoint.total_rows,
                    )
                except Exception as e:
                    logger.error("Row %d failed: %s", row_idx, e)
                    self.checkpoint_mgr.mark_failed(checkpoint, row_idx)
                    summary["failed"] += 1

                    write_row_result(config.output_file, {
                        "row_index": row_idx,
                        "product_name": row_data.get("product", row_data.get("name", "")),
                        "status": "failed",
                        "error": str(e),
                    })

        if summary["failed"] == 0:
            self.checkpoint_mgr.remove(config.input_file)
        else:
            logger.info("Checkpoint kept for %d failed rows", summary["failed"])
        elapsed = time.time() - checkpoint.started_at
        summary["elapsed_seconds"] = round(elapsed, 1)

        logger.info(
            "Pipeline complete: %d processed, %d failed, %d skipped in %.1fs",
            summary["processed"],
            summary["failed"],
            summary["skipped"],
            elapsed,
        )
        return summary

    def _process_row(self, row_data: dict, config: PipelineConfig, db_engine=None) -> dict:
        """Process a single row through the research graph."""
        query = self._extract_query(row_data)
        if not query:
            return {
                "row_index": row_data.get("__row_index", 0),
                "product_name": "",
                "status": "skipped",
                "error": "No query found in row",
            }

        focus = get_focus_config(config.focus_areas)

        if db_engine is None:
            db_engine = get_engine(DATABASE_URL)
        graph = build_graph()

        initial_state = create_initial_state(
            query=query,
            __row_index=row_data.get("__row_index", 0),
            focus_areas=[a.value for a in focus.areas],
            focus_config=focus.to_dict(),
            collect_specs=config.collect_specs,
            collect_media=config.collect_media,
            max_iterations=config.max_iterations,
        )

        final_state: dict = dict(initial_state)
        safe_recursion_limit = max(RECURSION_LIMIT, config.max_iterations * 8)
        try:
            for event in graph.stream(initial_state, {"recursion_limit": safe_recursion_limit}):
                for key, value in event.items():
                    if value:
                        final_state.update(value)
        except Exception as e:
            row_idx = row_data.get("__row_index", 0)
            logger.exception("Graph stream failed for row %s: %s", row_idx, e)
            final_state["status"] = "failed"
            final_state["error"] = str(e)

        _ok_statuses = ("done", "partial_complete", "complete", "max_iterations_reached")
        has_data = bool(
            final_state.get("images")
            or final_state.get("specifications")
            or final_state.get("status") in _ok_statuses
        )
        if not has_data:
            return {
                "row_index": row_data.get("__row_index", 0),
                "product_name": query,
                "status": "failed",
                "error": "Graph produced no output (recursion limit or crash)",
            }

        return extract_result_for_row(row_data, final_state)

    def _extract_query(self, row_data: dict) -> str:
        """Extract product query from a row dict."""
        for key in ["product", "query", "name", "title", "item", "product_name"]:
            if key in row_data and row_data[key]:
                return str(row_data[key]).strip()
        return ""

    def _estimate_rows(self, config: PipelineConfig) -> int:
        """Estimate total row count without loading all data."""
        from src.io.excel_reader import get_row_count
        total = get_row_count(config.input_file, config.sheet)
        return max(0, total - config.header_row)
