"""Base agent class with common utilities."""

from __future__ import annotations

from typing import Any

from src.config.logging import get_logger
from src.llm import get_llm, get_vision_llm


class BaseAgent:
    """Base class for all research agents.

    Provides common LLM access, logging, and state utilities.
    """

    name: str = "base"

    def __init__(self) -> None:
        self.logger = get_logger(f"agent.{self.name}")

    def get_llm(self, temperature: float = 0.0):
        """Get a language model instance."""
        return get_llm(temperature)

    def get_vision_llm(self, temperature: float = 0.0):
        """Get a vision-capable language model instance."""
        return get_vision_llm(temperature)

    def get_field(self, state: dict, key: str, default: Any = None) -> Any:
        """Safely get a field from state."""
        return state.get(key, default)

    def remove_tasks_by_type(self, tasks: list[dict], task_type: str) -> list[dict]:
        """Remove completed tasks of a given type."""
        return [t for t in tasks if t.get("type") != task_type]
