"""Plugin registry for nodes, tools, and agents.

Enables pluggable architecture where new components can be registered
and discovered at runtime without modifying core code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.config.logging import get_logger

logger = get_logger(__name__)


class Registry:
    """Central registry for nodes, tools, and agents.

    Usage:
        from src.core.registry import registry

        # Register a custom node
        @registry.node("my_custom_node")
        def my_node(state: dict) -> dict:
            return {"result": "done"}

        # Register a custom tool
        @registry.tool("my_custom_tool")
        def my_tool(query: str) -> str:
            return f"Result for {query}"

        # Retrieve registered components
        node_func = registry.get_node("my_custom_node")
        tool_func = registry.get_tool("my_custom_tool")
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Callable] = {}
        self._tools: dict[str, Callable] = {}
        self._agents: dict[str, Any] = {}
        self._graphs: dict[str, Any] = {}

    def node(self, name: str):
        """Decorator to register a node function."""
        def decorator(func: Callable) -> Callable:
            self._nodes[name] = func
            logger.debug("Registered node: %s", name)
            return func
        return decorator

    def tool(self, name: str):
        """Decorator to register a tool function."""
        def decorator(func: Callable) -> Callable:
            self._tools[name] = func
            logger.debug("Registered tool: %s", name)
            return func
        return decorator

    def agent(self, name: str, cls: Any) -> None:
        """Register an agent class."""
        self._agents[name] = cls
        logger.debug("Registered agent: %s", name)

    def graph(self, name: str, graph: Any) -> None:
        """Register a compiled graph."""
        self._graphs[name] = graph
        logger.debug("Registered graph: %s", name)

    def get_node(self, name: str) -> Callable | None:
        """Retrieve a registered node by name."""
        return self._nodes.get(name)

    def get_tool(self, name: str) -> Callable | None:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def get_agent(self, name: str) -> Any | None:
        """Retrieve a registered agent class by name."""
        return self._agents.get(name)

    def get_graph(self, name: str) -> Any | None:
        """Retrieve a registered graph by name."""
        return self._graphs.get(name)

    def list_nodes(self) -> list[str]:
        """List all registered node names."""
        return list(self._nodes.keys())

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def list_graphs(self) -> list[str]:
        """List all registered graph names."""
        return list(self._graphs.keys())

    def summary(self) -> dict[str, list[str]]:
        """Get a summary of all registered components."""
        return {
            "nodes": self.list_nodes(),
            "tools": self.list_tools(),
            "agents": self.list_agents(),
            "graphs": self.list_graphs(),
        }


# Global registry instance
registry = Registry()


def register_default_components() -> None:
    """Register the default nodes, tools, and agents.

    Called once at startup to populate the registry with built-in components.
    """
    from src.agents.coverage import CoverageAgent
    from src.agents.media_collector import MediaAgent
    from src.agents.planner import PlannerAgent
    from src.agents.researcher import ResearchAgent
    from src.agents.verifier import VerifierAgent
    from src.nodes.coverage import coverage, route_after_coverage
    from src.nodes.discovery import discovery
    from src.nodes.evidence import evidence
    from src.nodes.media import media
    from src.nodes.planner import planner
    from src.nodes.verification import verification
    from src.nodes.video_extract import video_extract

    # Register nodes
    registry._nodes["planner"] = planner
    registry._nodes["discover"] = discovery
    registry._nodes["evidence"] = evidence
    registry._nodes["media"] = media
    registry._nodes["video_extract"] = video_extract
    registry._nodes["verify"] = verification
    registry._nodes["coverage"] = coverage
    registry._nodes["route_after_coverage"] = route_after_coverage

    # Register agents
    registry._agents["planner"] = PlannerAgent
    registry._agents["researcher"] = ResearchAgent
    registry._agents["media"] = MediaAgent
    registry._agents["verifier"] = VerifierAgent
    registry._agents["coverage"] = CoverageAgent

    logger.info("Default components registered: %s", registry.summary())
