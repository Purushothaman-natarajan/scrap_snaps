"""Research agent - handles product discovery and evidence extraction."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
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

    def discover(self, state: dict) -> dict:
        """Discovery: web search -> extract product candidates."""
        self.logger.info("Research agent: discovery executing")
        query = state.get("query", "")

        search_queries = state.get("search_queries", [])
        if not search_queries:
            search_queries.append(f"{query} specifications official")

        current_query = search_queries[0]
        results = search_web.invoke({"query": current_query})

        llm = self.get_llm().with_structured_output(DiscoveryOutput)
        prompt = (
            f'Based on the following search results for the query "{query}", '
            f"identify the primary product being discussed.\n\n"
            f"Search Results:\n{results}"
        )

        try:
            extraction = llm.invoke(prompt)
            candidates = [c.model_dump() for c in extraction.candidates]
        except Exception as e:
            self.logger.warning("Discovery LLM failed: %s", e)
            candidates = [{"name": query, "canonical_name": query.upper(), "confidence": 0.5}]

        product = candidates[0] if candidates else None
        tasks = self.remove_tasks_by_type(state.get("tasks", []), "discover")

        return {
            "searched_queries": [current_query],
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

        search_q = f"{query} technical specifications"
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
