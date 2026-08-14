"""Database evidence tools."""

from langchain_core.tools import tool

from src.config import DATABASE_URL
from src.config.logging import get_logger

logger = get_logger(__name__)


@tool
def save_evidence(claim: dict) -> str:
    """Save an evidence claim to the database."""
    from src.db import Claim as ClaimModel
    from src.db import init_db

    session = init_db(DATABASE_URL)

    try:
        db_claim = ClaimModel(
            product_id=claim.get("product_id"),
            source_id=claim.get("source_id"),
            claim_type=claim.get("claim", ""),
            value=claim.get("value", ""),
            confidence=claim.get("confidence", 0.0),
        )
        session.add(db_claim)
        session.commit()
        return f"Saved claim: {claim.get('claim')} = {claim.get('value')}"
    except Exception as e:
        session.rollback()
        logger.error("Failed to save evidence: %s", e)
        return f"Failed to save claim: {e}"
    finally:
        session.close()
