from typing import Dict, Any, List
from src.state import ResearchState
from src.tools import search_web, fetch_page
from src.llm import get_llm
from pydantic import BaseModel, Field

class Claim(BaseModel):
    claim: str = Field(description="The specification name (e.g. 'weight', 'battery_life')")
    value: str = Field(description="The value of the specification")
    confidence: float = Field(description="Confidence in the extraction (0.0 to 1.0)")

class EvidenceOutput(BaseModel):
    claims: List[Claim] = Field(description="List of extracted claims/specifications")

def evidence(state: ResearchState) -> Dict[str, Any]:
    """
    Evidence Subgraph/Node (LLM-powered)
    Search -> Fetch Page -> Extract Claims.
    """
    print("--- EVIDENCE NODE ---")
    product = state.get("product", {})
    query = product.get("name", state.get("query", ""))
    
    # 1. Search for specs
    search_q = f"{query} technical specifications"
    results = search_web.invoke({"query": search_q})
    
    evidence_list = state.get("evidence", [])
    specs = state.get("specifications", {})
    
    if results:
        # 2. Fetch the top result page
        url = results[0].get("url")
        page_text = fetch_page.invoke({"url": url})
        
        # 3. Extract claims using LLM
        llm = get_llm().with_structured_output(EvidenceOutput)
        prompt = f"""
        Extract technical specifications for the product "{query}" from the following text.
        Source URL: {url}
        
        Text content:
        {page_text}
        """
        
        try:
            extraction = llm.invoke(prompt)
            for c in extraction.claims:
                claim_dict = c.dict()
                claim_dict["source"] = url
                claim_dict["source_type"] = "web" # simplfied
                evidence_list.append(claim_dict)
                specs[claim_dict["claim"]] = claim_dict["value"]
        except Exception as e:
            print(f"Evidence LLM failed: {e}")
            
    # Clean up task
    tasks = [t for t in state.get("tasks", []) if t.get("type") != "verify_spec"]
    
    return {
        "evidence": evidence_list,
        "specifications": specs,
        "tasks": tasks
    }
