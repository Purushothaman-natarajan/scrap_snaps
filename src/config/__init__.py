"""Configuration package for the research agent.

This module provides backward-compatible exports from the new settings structure.
"""

from src.config.logging import configure_logging, get_logger
from src.config.settings import settings

# Backward-compatible exports for existing imports from src.config
AZURE_API_KEY = settings.azure_api_key
AZURE_ENDPOINT = settings.azure_endpoint
AZURE_DEPLOYMENT = settings.azure_deployment
AZURE_CONSUMER_ID = settings.azure_consumer_id

DATABASE_URL = settings.database_url

MAX_ITERATIONS = settings.max_iterations
RECURSION_LIMIT = settings.recursion_limit
REQUIRED_VIEWS = settings.required_views_list
FOCUS_AREAS = settings.focus_areas
COLLECT_SPECS = settings.collect_specs
COLLECT_MEDIA = settings.collect_media

SERPAPI_KEY = settings.serpapi_key
RATE_LIMIT_INTERVAL = settings.rate_limit_interval
REQUEST_TIMEOUT = settings.request_timeout
USER_AGENT = settings.user_agent

PLAYWRIGHT_NAV_TIMEOUT = settings.playwright_nav_timeout
PLAYWRIGHT_SELECTOR_TIMEOUT = settings.playwright_selector_timeout

DOWNLOAD_DIR = settings.download_dir
MAX_IMAGE_RESULTS = settings.max_image_results
PAGE_TEXT_LIMIT = settings.page_text_limit
MAX_DOWNLOAD_SIZE = settings.max_download_size

VIDEO_DOWNLOAD_DIR = settings.video_download_dir
MAX_VIDEO_RESULTS = settings.max_video_results
VIDEO_MIN_DURATION = settings.video_min_duration
VIDEO_MAX_DURATION = settings.video_max_duration
VIDEO_FRAME_INTERVAL = settings.video_frame_interval
VIDEO_MAX_RESOLUTION = settings.video_max_resolution
AI_FRAME_SELECTION = settings.ai_frame_selection

VERIFICATION_WEIGHTS = settings.weights

SEARCH_CACHE_SIZE = settings.search_cache_size

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
    "FOCUS_AREAS",
    "COLLECT_SPECS",
    "COLLECT_MEDIA",
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
    "SEARCH_CACHE_SIZE",
    "validate_env",
]
