"""Streaming CSV reader for large files.

Mirrors excel_reader.read_excel_rows API: batch yield, header_row, __row_index.
Supports auto delimiter detection and multiple encodings.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CANDIDATE_DELIMITERS = [",", ";", "\t", "|"]


def _detect_delimiter(sample: str, configured: str) -> str:
    """Detect delimiter from sample if configured == 'auto'."""
    if configured != "auto":
        return configured
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters="".join(_CANDIDATE_DELIMITERS))
        if dialect.delimiter in _CANDIDATE_DELIMITERS:
            return dialect.delimiter
    except Exception:
        pass
    return ","


def _open_with_fallback(path: Path, encoding: str):
    """Open CSV with encoding fallback (utf-8-sig → utf-8 → latin1)."""
    encodings = [encoding]
    if encoding == "utf-8":
        encodings = ["utf-8-sig", "utf-8", "latin1"]
    elif encoding == "utf-8-sig":
        encodings = ["utf-8-sig", "latin1"]
    for enc in encodings:
        try:
            return open(path, newline="", encoding=enc)
        except Exception:
            continue
    return open(path, newline="", encoding=encoding)


def read_csv_rows(
    file_path: str | Path,
    header_row: int = 1,
    batch_size: int = 100,
    delimiter: str = "auto",
    encoding: str = "utf-8",
):
    """Stream rows from a CSV file as dictionaries.

    Args:
        file_path: Path to CSV.
        header_row: Row number containing headers (1-indexed).
        batch_size: Rows per batch.
        delimiter: auto or single char.
        encoding: File encoding.

    Yields:
        List of dicts keyed by header names.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size must be >=1, got {batch_size}")
    if header_row < 1:
        raise ValueError(f"header_row must be >=1, got {header_row}")

    file_path = Path(file_path)

    # Detect delimiter from sample
    effective_delimiter = delimiter
    if delimiter == "auto":
        try:
            with _open_with_fallback(file_path, encoding) as f:
                sample = f.read(8192)
                effective_delimiter = _detect_delimiter(sample, "auto")
        except Exception:
            effective_delimiter = ","

    f = _open_with_fallback(file_path, encoding)
    try:
        # Skip rows before header_row
        reader = csv.reader(f, delimiter=effective_delimiter)
        headers: list[str] = []
        batch: list[dict] = []

        for i, row in enumerate(reader, start=1):
            if i < header_row:
                continue
            if i == header_row:
                headers = [str(h).strip() if h is not None and str(h).strip() else f"col_{j}" for j, h in enumerate(row)]
                # Normalize duplicate headers
                seen: dict[str, int] = {}
                for idx, h in enumerate(headers):
                    if h in seen:
                        seen[h] += 1
                        headers[idx] = f"{h}_{seen[h]}"
                    else:
                        seen[h] = 0
                continue

            if not any(cell.strip() if isinstance(cell, str) else cell for cell in row):
                continue

            row_dict: dict = {}
            for j, val in enumerate(row):
                key = headers[j] if j < len(headers) else f"col_{j}"
                row_dict[key] = val
            row_dict["__row_index"] = i

            batch.append(row_dict)
            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch
    finally:
        try:
            f.close()
        except Exception:
            pass


def get_csv_row_count(file_path: str | Path, encoding: str = "utf-8") -> int:
    """Get total row count from CSV (including header)."""
    file_path = Path(file_path)
    count = 0
    with _open_with_fallback(file_path, encoding) as f:
        for _ in f:
            count += 1
    return count
