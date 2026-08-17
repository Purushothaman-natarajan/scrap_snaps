"""Streaming Excel writer for appending row results."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

logger = logging.getLogger(__name__)

RESULT_COLUMNS = [
    "row_index",
    "product_name",
    "status",
    "confidence",
    "specifications",
    "images_collected",
    "videos_collected",
    "image_paths",
    "video_paths",
    "error",
]

HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def _ensure_workbook(file_path: str | Path) -> None:
    """Create workbook with headers if it doesn't exist."""
    if os.path.exists(file_path):
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    for col, header in enumerate(RESULT_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 50
    ws.column_dimensions["F"].width = 16
    ws.column_dimensions["G"].width = 16
    ws.column_dimensions["H"].width = 60
    ws.column_dimensions["I"].width = 60
    ws.column_dimensions["J"].width = 40

    wb.save(file_path)
    wb.close()


def write_row_result(file_path: str | Path, result: dict) -> None:
    """Append a single row result to the Excel file.

    Args:
        file_path: Path to the Excel file.
        result: Dict with keys matching RESULT_COLUMNS.
    """
    file_path = str(file_path)
    _ensure_workbook(file_path)

    wb = load_workbook(file_path)
    ws = wb.active

    next_row = ws.max_row + 1 if ws.max_row else 2

    for col, key in enumerate(RESULT_COLUMNS, start=1):
        value = result.get(key, "")
        if isinstance(value, (list, dict)):
            import json
            value = json.dumps(value, default=str)
        ws.cell(row=next_row, column=col, value=value)

    wb.save(file_path)
    wb.close()


def write_row_results(file_path: str | Path, results: list[dict]) -> None:
    """Append multiple row results to the Excel file.

    Args:
        file_path: Path to the Excel file.
        results: List of dicts with keys matching RESULT_COLUMNS.
    """
    if not results:
        return

    file_path = str(file_path)
    _ensure_workbook(file_path)

    wb = load_workbook(file_path)
    ws = wb.active

    next_row = ws.max_row + 1 if ws.max_row else 2

    for result in results:
        for col, key in enumerate(RESULT_COLUMNS, start=1):
            value = result.get(key, "")
            if isinstance(value, (list, dict)):
                import json
                value = json.dumps(value, default=str)
            ws.cell(row=next_row, column=col, value=value)
        next_row += 1

    wb.save(file_path)
    wb.close()
