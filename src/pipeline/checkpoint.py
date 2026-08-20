"""Checkpoint manager for pipeline progress tracking.

Persists pipeline state (processed/failed rows, batch size, timing) to a
JSON file so interrupted runs can resume from where they left off.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field


@dataclass
class CheckpointData:
    """Serializable pipeline checkpoint."""

    input_file: str = ""
    output_file: str = ""
    total_rows: int = 0
    processed_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0
    completed_row_indices: list[int] = field(default_factory=list)
    failed_row_indices: list[int] = field(default_factory=list)
    started_at: float = 0.0
    last_updated: float = 0.0
    batch_size: int = 10

    @property
    def progress_pct(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return (self.processed_rows / self.total_rows) * 100

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CheckpointData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class CheckpointManager:
    """Manages pipeline checkpoints for crash recovery."""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

    def _checkpoint_path(self, input_file: str) -> str:
        import hashlib
        file_hash = hashlib.md5(input_file.encode()).hexdigest()[:8]
        return os.path.join(self.checkpoint_dir, f"checkpoint_{file_hash}.json")

    def load(self, input_file: str) -> CheckpointData | None:
        """Load existing checkpoint for an input file."""
        path = self._checkpoint_path(input_file)
        if not os.path.exists(path):
            return None

        with open(path) as f:
            data = json.load(f)
        return CheckpointData.from_dict(data)

    def save(self, checkpoint: CheckpointData) -> None:
        """Save checkpoint to disk."""
        checkpoint.last_updated = time.time()
        path = self._checkpoint_path(checkpoint.input_file)

        with open(path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

    def mark_completed(self, checkpoint: CheckpointData, row_index: int) -> None:
        """Mark a row as completed."""
        if row_index not in checkpoint.completed_row_indices:
            checkpoint.completed_row_indices.append(row_index)
        checkpoint.processed_rows = len(checkpoint.completed_row_indices)
        self.save(checkpoint)

    def mark_failed(self, checkpoint: CheckpointData, row_index: int) -> None:
        """Mark a row as failed."""
        if row_index not in checkpoint.failed_row_indices:
            checkpoint.failed_row_indices.append(row_index)
        checkpoint.failed_rows = len(checkpoint.failed_row_indices)
        self.save(checkpoint)

    def is_processed(self, checkpoint: CheckpointData, row_index: int) -> bool:
        """Check if a row has already been processed (completed or failed)."""
        return (
            row_index in checkpoint.completed_row_indices
            or row_index in checkpoint.failed_row_indices
        )

    def remove(self, input_file: str) -> None:
        """Remove checkpoint file."""
        path = self._checkpoint_path(input_file)
        if os.path.exists(path):
            os.remove(path)
