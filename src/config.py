"""Centralized configuration via environment variables."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# LLM
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-pro-latest")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///research.db")

# Execution
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "30"))
RECURSION_LIMIT = int(os.getenv("RECURSION_LIMIT", "50"))
REQUIRED_VIEWS = os.getenv("REQUIRED_VIEWS", "front,back,side,top").split(",")

# Networking
RATE_LIMIT_INTERVAL = float(os.getenv("RATE_LIMIT_INTERVAL", "1.0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10.0"))
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

# Playwright
PLAYWRIGHT_NAV_TIMEOUT = int(os.getenv("PLAYWRIGHT_NAV_TIMEOUT", "30000"))
PLAYWRIGHT_SELECTOR_TIMEOUT = int(os.getenv("PLAYWRIGHT_SELECTOR_TIMEOUT", "10000"))

# Scraping
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
MAX_IMAGE_RESULTS = int(os.getenv("MAX_IMAGE_RESULTS", "5"))
PAGE_TEXT_LIMIT = int(os.getenv("PAGE_TEXT_LIMIT", "5000"))
MAX_DOWNLOAD_SIZE = int(os.getenv("MAX_DOWNLOAD_SIZE", "10485760"))  # 10MB

# Verification scoring weights
VERIFICATION_WEIGHTS = {
    "identity": float(os.getenv("VERIFY_WEIGHT_IDENTITY", "0.30")),
    "evidence": float(os.getenv("VERIFY_WEIGHT_EVIDENCE", "0.25")),
    "image": float(os.getenv("VERIFY_WEIGHT_IMAGE", "0.30")),
    "base": float(os.getenv("VERIFY_WEIGHT_BASE", "0.15")),
}


def validate_env() -> bool:
    """Validate that required environment variables are set.

    Returns True if all required vars are present, False otherwise.
    """
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "your_google_api_key_here":
        logger.warning("GOOGLE_API_KEY is not set. LLM calls will fail.")
        return False
    return True
