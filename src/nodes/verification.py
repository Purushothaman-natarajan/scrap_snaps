from typing import Dict, Any
from src.state import ResearchState

SOURCE_PRIORITY = {
    "manufacturer": 1.00,
    "official_manual": 0.98,
    "official_product_page": 0.95,
    "authorized_retailer": 0.80,
    "major_review_site": 0.75,
    "youtube": 0.65,
    "marketplace": 0.50,
    "forum": 0.30,
}

def verification(state: ResearchState) -> Dict[str, Any]:
    """
    Verification Subgraph/Node
    Resolves conflicts, evaluates evidence quality based on source priority.
    """
    print("--- VERIFICATION NODE ---")
    
    evidence_list = state.get("evidence", [])
    images_list = state.get("images", [])
    
    # Calculate confidence scores
    identity_conf = state.get("product", {}).get("confidence", 0.0)
    
    # Mock evidence confidence (would resolve conflicts here)
    evidence_conf = 0.0
    if evidence_list:
        evidence_conf = sum(e.get("confidence", 0) * SOURCE_PRIORITY.get(e.get("source_type", "forum"), 0.3) for e in evidence_list) / len(evidence_list)
        
    image_conf = 0.0
    if images_list:
        image_conf = sum(img.get("confidence", 0.0) for img in images_list) / len(images_list)
        
    completion_score = (
        identity_conf * 0.30
        + evidence_conf * 0.25
        + image_conf * 0.30
        + 0.15 # source quality base
    )
    
    return {
        "confidence": completion_score
    }
