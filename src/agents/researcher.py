"""Research agent - handles product discovery and evidence extraction."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.search.focus import FocusConfig
from src.search.query_builder import build_queries
from src.tools.web import fetch_page, search_web


class ProductCandidate(BaseModel):
    """A candidate product identified from search results."""

    name: str = Field(description="The formal name of the product")
    canonical_name: str = Field(description="The normalized standard name")
    confidence: float = Field(description="Confidence this is the target product (0.0 to 1.0)")


class DiscoveryOutput(BaseModel):
    """Structured output from the discovery LLM call."""

    candidates: list[ProductCandidate] = Field(description="List of product candidates found")


class Claim(BaseModel):
    """An extracted technical specification claim."""

    claim: str = Field(description="The specification name (e.g. 'weight', 'battery_life')")
    value: str = Field(description="The value of the specification")
    confidence: float = Field(description="Confidence in the extraction (0.0 to 1.0)")


class EvidenceOutput(BaseModel):
    """Structured output from the evidence extraction LLM call."""

    claims: list[Claim] = Field(description="List of extracted claims/specifications")


class ResearchAgent(BaseAgent):
    """Research Agent - handles discovery and evidence extraction."""

    name = "researcher"

    def _get_focus(self, state: dict) -> FocusConfig:
        """Extract FocusConfig from state."""
        return FocusConfig.from_dict(state.get("focus_config", {}))

    def discover(self, state: dict) -> dict:
        """Discovery: web search -> extract product candidates."""
        self.logger.info("Research agent: discovery executing")
        query = state.get("query", "")
        focus = self._get_focus(state)

        # Build focus-aware queries
        queries = build_queries(query, focus=focus, task_type="discover", limit=3)
        if not queries:
            queries_list = [query]
        else:
            queries_list = [q.query for q in queries]

        # Search with first query
        current_query = queries_list[0]
        results = search_web.invoke({"query": current_query})

        # If no focus filtering, try additional queries
        if len(queries_list) > 1 and len(results) < 3:
            for q in queries_list[1:]:
                more = search_web.invoke({"query": q})
                results.extend(more)

        llm = self.get_llm().with_structured_output(DiscoveryOutput)
        prompt = (
            f'Based on the following search results for the query "{query}", '
            f"identify the primary product being discussed.\n\n"
            f"Search Results:\n{results}"
        )

        try:
            extraction = llm.invoke(prompt)
            from src.tools.usage import get_usage_tracker
            get_usage_tracker().record_llm(extraction)
            candidates = [c.model_dump() for c in extraction.candidates]
        except Exception as e:
            self.logger.warning("Discovery LLM failed: %s", e)
            candidates = [{"name": query, "canonical_name": query.upper(), "confidence": 0.5}]

        product = candidates[0] if candidates else None
        tasks = self.remove_tasks_by_type(state.get("tasks", []), "discover")

        return {
            "searched_queries": queries_list,
            "candidates": candidates,
            "product": product,
            "sources": results,
            "tasks": tasks,
        }

    def extract_evidence(self, state: dict) -> dict:
        """Evidence extraction: search -> fetch page -> extract specs."""
        self.logger.info("Research agent: evidence extraction executing")
        product = state.get("product", {})
        query = product.get("name", state.get("query", ""))
        focus = self._get_focus(state)

        # Build focus-aware queries for specs
        queries = build_queries(query, focus=focus, task_type="verify_spec", limit=2)
        search_q = queries[0].query if queries else f"{query} technical specifications"

        results = search_web.invoke({"query": search_q})

        evidence_list = state.get("evidence", [])
        specs = state.get("specifications", {})

        if results:
            url = results[0].get("url")
            page_text = fetch_page.invoke({"url": url})

            llm = self.get_llm().with_structured_output(EvidenceOutput)
            prompt = (
                f'Extract technical specifications for the product "{query}" from the text below.\n'
                f"Source URL: {url}\n\nText content:\n{page_text}"
            )

            try:
                extraction = llm.invoke(prompt)
                from src.tools.usage import get_usage_tracker
                get_usage_tracker().record_llm(extraction)
                for c in extraction.claims:
                    claim_dict = c.model_dump()
                    claim_dict["source"] = url
                    claim_dict["source_type"] = "web"
                    evidence_list.append(claim_dict)
                    specs[claim_dict["claim"]] = claim_dict["value"]
            except Exception as e:
                self.logger.warning("Evidence LLM failed: %s", e)

        tasks = self.remove_tasks_by_type(state.get("tasks", []), "verify_spec")
        return {"evidence": evidence_list, "specifications": specs, "tasks": tasks}
