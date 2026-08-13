from typing import Dict, Any, List
from src.state import ResearchState
from src.tools import search_web
from src.llm import get_llm
from pydantic import BaseModel, Field

class ProductCandidate(BaseModel):
    name: str = Field(description="The formal name of the product")
    canonical_name: str = Field(description="The normalized standard name")
    confidence: float = Field(description="Confidence that this is the target product (0.0 to 1.0)")

class DiscoveryOutput(BaseModel):
    candidates: List[ProductCandidate] = Field(description="List of product candidates found")

def discovery(state: ResearchState) -> Dict[str, Any]:
    """
    Discovery Subgraph/Node (LLM-powered)
    Web search -> rank sources -> extract candidates -> canonicalize product identity.
    """
    print("--- DISCOVERY NODE ---")
    query = state.get("query", "")
    
    search_queries = state.get("search_queries", [])
    if not search_queries:
        search_queries.append(f"{query} specifications official")
        
    current_query = search_queries[0]
    
    # Execute actual search
    results = search_web.invoke({"query": current_query})
    
    # Extract candidate using LLM
    llm = get_llm().with_structured_output(DiscoveryOutput)
    prompt = f"""
    Based on the following search results for the query "{query}", identify the primary product being discussed.
    
    Search Results:
    {results}
    """
    
    try:
        extraction = llm.invoke(prompt)
        candidates = [c.dict() for c in extraction.candidates]
    except Exception as e:
        print(f"Discovery LLM failed: {e}")
        candidates = [{
            "name": query,
            "canonical_name": query.upper(),
            "confidence": 0.5
        }]
        
    product = candidates[0] if candidates else None
    
    # Remove processed task
    tasks = [t for t in state.get("tasks", []) if t.get("type") != "discover"]
    
    return {
        "searched_queries": [current_query],
        "candidates": candidates,
        "product": product,
        "sources": results,
        "tasks": tasks
    }
