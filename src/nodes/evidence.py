"""Evidence node - extract technical specifications from web pages."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src.llm import get_llm
from src.state import ResearchState
from src.tools import fetch_page, search_web

logger = logging.getLogger(__name__)


class Claim(BaseModel):
    """An extracted technical specification claim."""

    claim: str = Field(description="The specification name (e.g. 'weight', 'battery_life')")
    value: str = Field(description="The value of the specification")
    confidence: float = Field(description="Confidence in the extraction (0.0 to 1.0)")


class EvidenceOutput(BaseModel):
    """Structured output from the evidence extraction LLM call."""

    claims: list[Claim] = Field(description="List of extracted claims/specifications")


def evidence(state: ResearchState) -> dict:
    """Evidence Node (LLM-powered).

    Search -> Fetch Page -> Extract Claims.
    """
    logger.info("Evidence node executing")
    product = state.get("product", {})
    query = product.get("name", state.get("query", ""))

    search_q = f"{query} technical specifications"
    results = search_web.invoke({"query": search_q})

    evidence_list = state.get("evidence", [])
    specs = state.get("specifications", {})

    if results:
        # Use only the top search result for now. In a full system, we'd
        # fetch multiple results and merge/deduplicate the extracted claims.
        url = results[0].get("url")
        page_text = fetch_page.invoke({"url": url})

        llm = get_llm().with_structured_output(EvidenceOutput)
        prompt = (
            f'Extract technical specifications for the product "{query}" from the text below.\n'
            f"Source URL: {url}\n\nText content:\n{page_text}"
        )

        try:
            extraction = llm.invoke(prompt)
            for c in extraction.claims:
                claim_dict = c.model_dump()
                claim_dict["source"] = url
                # All claims from web search are tagged as "web" source type.
                # In a full system, this would be parsed from the URL or page metadata.
                claim_dict["source_type"] = "web"
                evidence_list.append(claim_dict)
                specs[claim_dict["claim"]] = claim_dict["value"]
        except Exception as e:
            logger.warning("Evidence LLM failed: %s", e)

    tasks = [t for t in state.get("tasks", []) if t.get("type") != "verify_spec"]

    return {"evidence": evidence_list, "specifications": specs, "tasks": tasks}
