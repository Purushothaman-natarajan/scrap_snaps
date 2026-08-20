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
PLAYWRIGHT_HEADLESS = settings.playwright_headless

DOWNLOAD_DIR = settings.download_dir
MAX_IMAGE_RESULTS = settings.max_image_results
PAGE_TEXT_LIMIT = settings.page_text_limit
MAX_DOWNLOAD_SIZE = settings.max_download_size

# Image extraction
IMAGE_BATCH_SIZE = settings.image_batch_size
IMAGE_DOWNLOAD_LIMIT = settings.image_download_limit
IMAGE_CROP_RATIO = settings.image_crop_ratio
IMAGE_ANALYZE_CACHE_TTL = settings.image_analyze_cache_ttl
ANALYZE_CACHE_MAX_SIZE = settings.analyze_cache_max_size

# Video extraction
VIDEO_DOWNLOAD_DIR = settings.video_download_dir
MAX_VIDEO_RESULTS = settings.max_video_results
VIDEO_MIN_DURATION = settings.video_min_duration
VIDEO_MAX_DURATION = settings.video_max_duration
VIDEO_FRAME_INTERVAL = settings.video_frame_interval
VIDEO_MAX_RESOLUTION = settings.video_max_resolution
AI_FRAME_SELECTION = settings.ai_frame_selection
CROP_VIDEO_FRAMES = settings.crop_video_frames
VIDEO_SCENE_THRESHOLD = settings.video_scene_threshold
VIDEO_FRAME_JPEG_QUALITY = settings.video_frame_jpeg_quality
VIDEO_MAX_FRAMES_PER_VIEW = settings.video_max_frames_per_view
VIDEO_AI_SELECTION_MAX_FRAMES = settings.video_ai_selection_max_frames

# Perceptual hashing
PHASH_SIMILARITY_THRESHOLD = settings.phash_similarity_threshold

# Coverage / termination
COVERAGE_MAX_CYCLES = settings.coverage_max_cycles
COVERAGE_NO_PROGRESS_THRESHOLD = settings.coverage_no_progress_threshold
COVERAGE_PROXIMITY_RATIO = settings.coverage_proximity_ratio

# Search query building
SEARCH_DOMAINS_PER_AREA = settings.search_domains_per_area
SEARCH_MODIFIERS_PER_AREA = settings.search_modifiers_per_area
SEARCH_QUERIES_PER_TASK = settings.search_queries_per_task

VERIFICATION_WEIGHTS = settings.weights

SEARCH_CACHE_SIZE = settings.search_cache_size
SERPAPI_MAX_HITS_PER_ROW = settings.serpapi_max_hits_per_row
FAILED_URL_TTL = settings.failed_url_ttl
LOG_VERBOSE = settings.log_verbose

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
    "PLAYWRIGHT_HEADLESS",
    "DOWNLOAD_DIR",
    "MAX_IMAGE_RESULTS",
    "PAGE_TEXT_LIMIT",
    "MAX_DOWNLOAD_SIZE",
    "IMAGE_BATCH_SIZE",
    "IMAGE_DOWNLOAD_LIMIT",
    "IMAGE_CROP_RATIO",
    "IMAGE_ANALYZE_CACHE_TTL",
    "ANALYZE_CACHE_MAX_SIZE",
    "VIDEO_DOWNLOAD_DIR",
    "MAX_VIDEO_RESULTS",
    "VIDEO_MIN_DURATION",
    "VIDEO_MAX_DURATION",
    "VIDEO_FRAME_INTERVAL",
    "VIDEO_MAX_RESOLUTION",
    "AI_FRAME_SELECTION",
    "CROP_VIDEO_FRAMES",
    "VIDEO_SCENE_THRESHOLD",
    "VIDEO_FRAME_JPEG_QUALITY",
    "VIDEO_MAX_FRAMES_PER_VIEW",
    "VIDEO_AI_SELECTION_MAX_FRAMES",
    "PHASH_SIMILARITY_THRESHOLD",
    "COVERAGE_MAX_CYCLES",
    "COVERAGE_NO_PROGRESS_THRESHOLD",
    "COVERAGE_PROXIMITY_RATIO",
    "SEARCH_DOMAINS_PER_AREA",
    "SEARCH_MODIFIERS_PER_AREA",
    "SEARCH_QUERIES_PER_TASK",
    "VERIFICATION_WEIGHTS",
    "SEARCH_CACHE_SIZE",
    "SERPAPI_MAX_HITS_PER_ROW",
    "FAILED_URL_TTL",
    "LOG_VERBOSE",
    "validate_env",
]
