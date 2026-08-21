"""Unified reader for CSV and Excel inputs.

Auto-detects file type by extension and delegates to the appropriate
streaming reader. Pipeline runner uses this instead of direct
excel_reader to support both .csv and .xlsx/.xls.
"""

from __future__ import annotations

from pathlib import Path


def read_rows(
    file_path: str | Path,
    sheet: str | None = None,
    header_row: int = 1,
    batch_size: int = 100,
    delimiter: str = "auto",
    encoding: str = "utf-8",
):
    """Yield batches of row dicts from CSV or Excel.

    Dispatches based on file suffix:
      .csv  -> csv_reader.read_csv_rows
      else  -> excel_reader.read_excel_rows (sheet is used)

    All other args mirror the underlying readers.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix == ".csv":
        from src.io.csv_reader import read_csv_rows

        yield from read_csv_rows(file_path, header_row=header_row, batch_size=batch_size, delimiter=delimiter, encoding=encoding)
    else:
        from src.io.excel_reader import read_excel_rows

        yield from read_excel_rows(file_path, sheet=sheet, header_row=header_row, batch_size=batch_size)


def get_row_count_unified(file_path: str | Path, sheet: str | None = None, encoding: str = "utf-8") -> int:
    """Get total row count for CSV or Excel."""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".csv":
        from src.io.csv_reader import get_csv_row_count

        return get_csv_row_count(file_path, encoding=encoding)
    else:
        from src.io.excel_reader import get_row_count

        return get_row_count(file_path, sheet=sheet)
