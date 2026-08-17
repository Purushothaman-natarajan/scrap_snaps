"""Configuration compatibility layer - imports from new settings structure.

This module maintains backward compatibility for existing imports while
using the new Pydantic Settings internally.
"""

from src.config.settings import settings

# LLM (Azure OpenAI)
AZURE_API_KEY = settings.llm.azure_api_key
AZURE_ENDPOINT = settings.llm.azure_endpoint
AZURE_DEPLOYMENT = settings.llm.azure_deployment
AZURE_CONSUMER_ID = settings.llm.azure_consumer_id

# Database
DATABASE_URL = settings.database.url

# Execution
MAX_ITERATIONS = settings.execution.max_iterations
RECURSION_LIMIT = settings.execution.recursion_limit
REQUIRED_VIEWS = settings.execution.required_views_list

# Networking
SERPAPI_KEY = settings.network.serpapi_key
RATE_LIMIT_INTERVAL = settings.network.rate_limit_interval
REQUEST_TIMEOUT = settings.network.request_timeout
USER_AGENT = settings.network.user_agent

# Playwright
PLAYWRIGHT_NAV_TIMEOUT = settings.playwright.nav_timeout
PLAYWRIGHT_SELECTOR_TIMEOUT = settings.playwright.selector_timeout

# Scraping
DOWNLOAD_DIR = settings.scraping.download_dir
MAX_IMAGE_RESULTS = settings.scraping.max_image_results
PAGE_TEXT_LIMIT = settings.scraping.page_text_limit
MAX_DOWNLOAD_SIZE = settings.scraping.max_download_size

# Video extraction
VIDEO_DOWNLOAD_DIR = settings.video.download_dir
MAX_VIDEO_RESULTS = settings.video.max_results
VIDEO_MIN_DURATION = settings.video.min_duration
VIDEO_MAX_DURATION = settings.video.max_duration
VIDEO_FRAME_INTERVAL = settings.video.frame_interval
VIDEO_MAX_RESOLUTION = settings.video.max_resolution
AI_FRAME_SELECTION = settings.video.ai_frame_selection

# Verification scoring weights
VERIFICATION_WEIGHTS = settings.verification.weights


def validate_env() -> bool:
    """Validate that required environment variables are set.

    Returns True if all required vars are present, False otherwise.
    """
    missing = settings.validate_required()
    if missing:
        from src.config.logging import get_logger
        logger = get_logger(__name__)
        for key in missing:
            logger.warning(f"{key} is not set. LLM calls will fail.")
        return False
    return True
