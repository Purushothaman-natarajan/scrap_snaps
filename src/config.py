"""Configuration compatibility layer - imports from new settings structure.

This module maintains backward compatibility for existing imports while
using the new Pydantic Settings internally.
"""

from src.config.settings import settings

# LLM (Azure OpenAI)
AZURE_API_KEY = settings.azure_api_key
AZURE_ENDPOINT = settings.azure_endpoint
AZURE_DEPLOYMENT = settings.azure_deployment
AZURE_CONSUMER_ID = settings.azure_consumer_id

# Database
DATABASE_URL = settings.database_url

# Execution
MAX_ITERATIONS = settings.max_iterations
RECURSION_LIMIT = settings.recursion_limit
REQUIRED_VIEWS = settings.required_views_list

# Networking
SERPAPI_KEY = settings.serpapi_key
RATE_LIMIT_INTERVAL = settings.rate_limit_interval
REQUEST_TIMEOUT = settings.request_timeout
USER_AGENT = settings.user_agent

# Playwright
PLAYWRIGHT_NAV_TIMEOUT = settings.playwright_nav_timeout
PLAYWRIGHT_SELECTOR_TIMEOUT = settings.playwright_selector_timeout

# Scraping
DOWNLOAD_DIR = settings.download_dir
MAX_IMAGE_RESULTS = settings.max_image_results
PAGE_TEXT_LIMIT = settings.page_text_limit
MAX_DOWNLOAD_SIZE = settings.max_download_size

# Video extraction
VIDEO_DOWNLOAD_DIR = settings.video_download_dir
MAX_VIDEO_RESULTS = settings.max_video_results
VIDEO_MIN_DURATION = settings.video_min_duration
VIDEO_MAX_DURATION = settings.video_max_duration
VIDEO_FRAME_INTERVAL = settings.video_frame_interval
VIDEO_MAX_RESOLUTION = settings.video_max_resolution
AI_FRAME_SELECTION = settings.ai_frame_selection

# Verification scoring weights
VERIFICATION_WEIGHTS = settings.weights


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
