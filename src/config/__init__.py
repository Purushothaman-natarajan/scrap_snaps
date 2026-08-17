"""Configuration package for the research agent.

This module provides backward-compatible exports from the new settings structure.
"""

from src.config.logging import configure_logging, get_logger
from src.config.settings import settings

# Backward-compatible exports for existing imports from src.config
AZURE_API_KEY = settings.llm.azure_api_key
AZURE_ENDPOINT = settings.llm.azure_endpoint
AZURE_DEPLOYMENT = settings.llm.azure_deployment
AZURE_CONSUMER_ID = settings.llm.azure_consumer_id

DATABASE_URL = settings.database.url

MAX_ITERATIONS = settings.execution.max_iterations
RECURSION_LIMIT = settings.execution.recursion_limit
REQUIRED_VIEWS = settings.execution.required_views_list

SERPAPI_KEY = settings.network.serpapi_key
RATE_LIMIT_INTERVAL = settings.network.rate_limit_interval
REQUEST_TIMEOUT = settings.network.request_timeout
USER_AGENT = settings.network.user_agent

PLAYWRIGHT_NAV_TIMEOUT = settings.playwright.nav_timeout
PLAYWRIGHT_SELECTOR_TIMEOUT = settings.playwright.selector_timeout

DOWNLOAD_DIR = settings.scraping.download_dir
MAX_IMAGE_RESULTS = settings.scraping.max_image_results
PAGE_TEXT_LIMIT = settings.scraping.page_text_limit
MAX_DOWNLOAD_SIZE = settings.scraping.max_download_size

VIDEO_DOWNLOAD_DIR = settings.video.download_dir
MAX_VIDEO_RESULTS = settings.video.max_results
VIDEO_MIN_DURATION = settings.video.min_duration
VIDEO_MAX_DURATION = settings.video.max_duration
VIDEO_FRAME_INTERVAL = settings.video.frame_interval
VIDEO_MAX_RESOLUTION = settings.video.max_resolution
AI_FRAME_SELECTION = settings.video.ai_frame_selection

VERIFICATION_WEIGHTS = settings.verification.weights

validate_env = settings.validate_required

__all__ = [
    "settings",
    "configure_logging",
    "get_logger",
    "AZURE_API_KEY",
    "AZURE_ENDPOINT",
    "AZURE_DEPLOYMENT",
    "AZURE_CONSUMER_ID",
    "DATABASE_URL",
    "MAX_ITERATIONS",
    "RECURSION_LIMIT",
    "REQUIRED_VIEWS",
    "SERPAPI_KEY",
    "RATE_LIMIT_INTERVAL",
    "REQUEST_TIMEOUT",
    "USER_AGENT",
    "PLAYWRIGHT_NAV_TIMEOUT",
    "PLAYWRIGHT_SELECTOR_TIMEOUT",
    "DOWNLOAD_DIR",
    "MAX_IMAGE_RESULTS",
    "PAGE_TEXT_LIMIT",
    "MAX_DOWNLOAD_SIZE",
    "VIDEO_DOWNLOAD_DIR",
    "MAX_VIDEO_RESULTS",
    "VIDEO_MIN_DURATION",
    "VIDEO_MAX_DURATION",
    "VIDEO_FRAME_INTERVAL",
    "VIDEO_MAX_RESOLUTION",
    "AI_FRAME_SELECTION",
    "VERIFICATION_WEIGHTS",
    "validate_env",
]
