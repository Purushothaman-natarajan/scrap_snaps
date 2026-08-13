"""Verification node - evaluate evidence quality and resolve conflicts."""

from __future__ import annotations

import logging

from src.config import VERIFICATION_WEIGHTS
from src.state import ResearchState

logger = logging.getLogger(__name__)

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


def verification(state: ResearchState) -> dict:
    """Verification Node.

    Resolves conflicts, evaluates evidence quality based on source priority.
    """
    logger.info("Verification node executing")

    evidence_list = state.get("evidence", [])
    images_list = state.get("images", [])

    identity_conf = state.get("product", {}).get("confidence", 0.0)

    evidence_conf = 0.0
    if evidence_list:
        # Weighted average: each claim's confidence is multiplied by its source's
        # reliability score. Manufacturer sources (1.0) count more than forums (0.3).
        evidence_conf = (
            sum(
                e.get("confidence", 0) * SOURCE_PRIORITY.get(e.get("source_type", "forum"), 0.3)
                for e in evidence_list
            )
            / len(evidence_list)
        )

    image_conf = 0.0
    if images_list:
        image_conf = sum(img.get("confidence", 0.0) for img in images_list) / len(images_list)

    w = VERIFICATION_WEIGHTS
    # Final score is a weighted sum of all confidence dimensions plus a base
    # score. The base ensures even empty results get a non-zero score.
    completion_score = (
        identity_conf * w["identity"]
        + evidence_conf * w["evidence"]
        + image_conf * w["image"]
        + w["base"]
    )

    return {"confidence": completion_score}
