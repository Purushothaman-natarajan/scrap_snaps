from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src.llm import get_llm
from src.state import ResearchState
from src.tools import search_web

logger = logging.getLogger(__name__)


class ProductCandidate(BaseModel):
    """A candidate product identified from search results."""

    name: str = Field(description="The formal name of the product")
    canonical_name: str = Field(description="The normalized standard name")
    confidence: float = Field(description="Confidence this is the target product (0.0 to 1.0)")


class DiscoveryOutput(BaseModel):
    """Structured output from the discovery LLM call."""

    candidates: list[ProductCandidate] = Field(description="List of product candidates found")


def discovery(state: ResearchState) -> dict:
    """Discovery Node (LLM-powered).

    Web search -> rank sources -> extract candidates -> canonicalize product identity.
    """
    logger.info("Discovery node executing")
    query = state.get("query", "")

    search_queries = state.get("search_queries", [])
    if not search_queries:
        search_queries.append(f"{query} specifications official")

    current_query = search_queries[0]

    results = search_web.invoke({"query": current_query})

    llm = get_llm().with_structured_output(DiscoveryOutput)
    prompt = (
        f'Based on the following search results for the query "{query}", '
        f"identify the primary product being discussed.\n\n"
        f"Search Results:\n{results}"
    )

    try:
        extraction = llm.invoke(prompt)
        candidates = [c.model_dump() for c in extraction.candidates]
    except Exception as e:
        logger.warning("Discovery LLM failed: %s", e)
        candidates = [{"name": query, "canonical_name": query.upper(), "confidence": 0.5}]

    product = candidates[0] if candidates else None

    tasks = [t for t in state.get("tasks", []) if t.get("type") != "discover"]

    return {
        "searched_queries": [current_query],
        "candidates": candidates,
        "product": product,
        "sources": results,
        "tasks": tasks,
    }
