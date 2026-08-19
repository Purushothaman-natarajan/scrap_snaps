"""Pipeline runner - batch orchestrator for processing Excel rows."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src.io import get_storage, read_excel_rows, write_row_result
from src.pipeline.checkpoint import CheckpointData, CheckpointManager
from src.pipeline.results import extract_result_for_row

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
    collect_media: str = "both"
    focus_areas: str = ""
    max_iterations: int = 30
    storage_backend: str = "local"
    storage_base_dir: str = "downloads"
    skip_existing: bool = True

    @classmethod
    def from_json(cls, path: str) -> PipelineConfig:
        """Load config from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

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
        from src.config import DATABASE_URL
        from src.db import get_engine
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

                try:
                    result = self._process_row(row_data, config, db_engine=db_engine)
                    write_row_result(config.output_file, result)

                    # Save to database
                    try:
                        from src.config import DATABASE_URL
                        from src.db.utils import save_result_to_db
                        save_result_to_db(result, DATABASE_URL)
                    except Exception as db_err:
                        logger.warning("Failed to save to DB for row %d: %s", row_idx, db_err)

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

        self.checkpoint_mgr.remove(config.input_file)
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
        from src.config import DATABASE_URL, RECURSION_LIMIT, REQUIRED_VIEWS
        from src.db import get_engine
        from src.graph import build_graph
        from src.search.focus import get_focus_config

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

        initial_state = {
            "query": query,
            "__row_index": row_data.get("__row_index", 0),
            "focus_areas": [a.value for a in focus.areas],
            "focus_config": focus.to_dict(),
            "collect_specs": config.collect_specs,
            "collect_media": config.collect_media,
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
            "max_iterations": config.max_iterations,
            "confidence": 0.0,
            "status": "started",
        }

        final_state = None
        for event in graph.stream(initial_state, {"recursion_limit": RECURSION_LIMIT}):
            for key, value in event.items():
                final_state = value

        if final_state is None:
            return {
                "row_index": row_data.get("__row_index", 0),
                "product_name": query,
                "status": "failed",
                "error": "Graph produced no output",
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
