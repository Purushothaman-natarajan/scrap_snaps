"""YAML configuration loader.

Loads settings from ``config.yaml`` as the single source of truth for all
non-credential configuration. Credentials (API keys, endpoints, database
URLs) remain in ``.env`` for security.

The YAML file uses sections that map to flat Settings field names via
an explicit mapping. Environment variables still override YAML values
for credentials (AZURE_*, SERPAPI_KEY, DATABASE_URL).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config.yaml"

# Fields that ALWAYS come from .env (credentials / secrets)
_CREDENTIAL_KEYS = {
    "AZURE_API_KEY",
    "AZURE_ENDPOINT",
    "AZURE_DEPLOYMENT",
    "AZURE_CONSUMER_ID",
    "SERPAPI_KEY",
    "DATABASE_URL",
}

# Mapping: (yaml_section, yaml_key) -> settings_field_name
# None section means top-level key
_YAML_TO_SETTINGS: dict[tuple[str | None, str], str] = {
    # execution
    (None, "max_iterations"): "MAX_ITERATIONS",
    (None, "recursion_limit"): "RECURSION_LIMIT",
    (None, "required_views"): "REQUIRED_VIEWS",
    ("execution", "max_iterations"): "MAX_ITERATIONS",
    ("execution", "recursion_limit"): "RECURSION_LIMIT",
    ("execution", "required_views"): "REQUIRED_VIEWS",
    # focus
    (None, "focus_areas"): "FOCUS_AREAS",
    (None, "collect_specs"): "COLLECT_SPECS",
    (None, "collect_media"): "COLLECT_MEDIA",
    ("focus", "areas"): "FOCUS_AREAS",
    ("focus", "collect_specs"): "COLLECT_SPECS",
    ("focus", "collect_media"): "COLLECT_MEDIA",
    # networking
    ("networking", "rate_limit_interval"): "RATE_LIMIT_INTERVAL",
    ("networking", "request_timeout"): "REQUEST_TIMEOUT",
    ("networking", "user_agent"): "USER_AGENT",
    # playwright
    ("playwright", "nav_timeout"): "PLAYWRIGHT_NAV_TIMEOUT",
    ("playwright", "selector_timeout"): "PLAYWRIGHT_SELECTOR_TIMEOUT",
    ("playwright", "headless"): "PLAYWRIGHT_HEADLESS",
    # scraping
    ("scraping", "download_dir"): "DOWNLOAD_DIR",
    ("scraping", "max_image_results"): "MAX_IMAGE_RESULTS",
    ("scraping", "page_text_limit"): "PAGE_TEXT_LIMIT",
    ("scraping", "max_download_size"): "MAX_DOWNLOAD_SIZE",
    # image
    ("image", "batch_size"): "IMAGE_BATCH_SIZE",
    ("image", "download_limit"): "IMAGE_DOWNLOAD_LIMIT",
    ("image", "crop_ratio"): "IMAGE_CROP_RATIO",
    ("image", "analyze_cache_ttl"): "IMAGE_ANALYZE_CACHE_TTL",
    ("image", "analyze_cache_max_size"): "ANALYZE_CACHE_MAX_SIZE",
    # video
    ("video", "download_dir"): "VIDEO_DOWNLOAD_DIR",
    ("video", "max_results"): "MAX_VIDEO_RESULTS",
    ("video", "min_duration"): "VIDEO_MIN_DURATION",
    ("video", "max_duration"): "VIDEO_MAX_DURATION",
    ("video", "frame_interval"): "VIDEO_FRAME_INTERVAL",
    ("video", "max_resolution"): "VIDEO_MAX_RESOLUTION",
    ("video", "crop_frames"): "CROP_VIDEO_FRAMES",
    ("video", "ai_frame_selection"): "AI_FRAME_SELECTION",
    ("video", "scene_threshold"): "VIDEO_SCENE_THRESHOLD",
    ("video", "frame_jpeg_quality"): "VIDEO_FRAME_JPEG_QUALITY",
    ("video", "max_frames_per_view"): "VIDEO_MAX_FRAMES_PER_VIEW",
    ("video", "ai_selection_max_frames"): "VIDEO_AI_SELECTION_MAX_FRAMES",
    # hashing
    ("hashing", "similarity_threshold"): "PHASH_SIMILARITY_THRESHOLD",
    # coverage
    ("coverage", "max_cycles"): "COVERAGE_MAX_CYCLES",
    ("coverage", "no_progress_threshold"): "COVERAGE_NO_PROGRESS_THRESHOLD",
    ("coverage", "proximity_ratio"): "COVERAGE_PROXIMITY_RATIO",
    # search
    ("search", "domains_per_area"): "SEARCH_DOMAINS_PER_AREA",
    ("search", "modifiers_per_area"): "SEARCH_MODIFIERS_PER_AREA",
    ("search", "queries_per_task"): "SEARCH_QUERIES_PER_TASK",
    ("search", "cache_size"): "SEARCH_CACHE_SIZE",
    ("search", "serpapi_max_hits_per_row"): "SERPAPI_MAX_HITS_PER_ROW",
    # failure
    ("failure", "url_ttl"): "FAILED_URL_TTL",
    # verification
    ("verification", "weight_identity"): "VERIFY_WEIGHT_IDENTITY",
    ("verification", "weight_evidence"): "VERIFY_WEIGHT_EVIDENCE",
    ("verification", "weight_image"): "VERIFY_WEIGHT_IMAGE",
    ("verification", "weight_base"): "VERIFY_WEIGHT_BASE",
    # logging
    ("logging", "level"): "LOG_LEVEL",
    ("logging", "json"): "LOG_JSON",
    ("logging", "timestamp"): "LOG_TIMESTAMP",
    ("logging", "capture"): "LOG_CAPTURE",
    ("logging", "file"): "LOG_FILE",
    ("logging", "verbose"): "LOG_VERBOSE",
}


def _load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file and return the raw dict."""
    path = Path(path)
    if not path.exists():
        logger.debug("Config file not found: %s", path)
        return {}

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        logger.warning("Config file is empty or not a dict: %s", path)
        return {}

    return raw


def _convert_value(value: Any) -> Any:
    """Convert YAML value to match Settings field types."""
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return ",".join(str(v) for v in value)
    return value


def load_config_yaml(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load config.yaml and return a dict suitable for Settings.

    Returns a flat dict where:
    - Non-credential keys come from the YAML file via explicit mapping
    - Credential keys come from environment variables (never from YAML)
    """
    raw = _load_yaml(path)
    if not raw:
        return {}

    result: dict[str, Any] = {}

    # Credentials always from env
    for key in _CREDENTIAL_KEYS:
        env_val = os.environ.get(key)
        if env_val is not None:
            result[key] = env_val

    # Walk YAML sections and map to Settings field names
    for section_key, section_val in raw.items():
        if section_key in ("pipeline",):
            continue  # pipeline section handled separately

        if isinstance(section_val, dict):
            for yaml_key, yaml_value in section_val.items():
                mapping_key = (section_key, yaml_key)
                if mapping_key in _YAML_TO_SETTINGS:
                    settings_key = _YAML_TO_SETTINGS[mapping_key]
                    if settings_key in _CREDENTIAL_KEYS:
                        continue
                    env_val = os.environ.get(settings_key)
                    if env_val is not None:
                        result[settings_key] = env_val
                    else:
                        result[settings_key] = _convert_value(yaml_value)
        else:
            # Top-level key (shouldn't happen in sectioned YAML, but handle it)
            mapping_key = (None, section_key)
            if mapping_key in _YAML_TO_SETTINGS:
                settings_key = _YAML_TO_SETTINGS[mapping_key]
                if settings_key not in _CREDENTIAL_KEYS:
                    env_val = os.environ.get(settings_key)
                    if env_val is not None:
                        result[settings_key] = env_val
                    else:
                        result[settings_key] = _convert_value(section_val)

    logger.debug("Loaded %d settings from %s", len(result), path)
    return result


def get_pipeline_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load pipeline-specific settings from config.yaml.

    Returns the ``pipeline:`` section of config.yaml as a dict,
    with env var overrides for applicable fields.
    """
    path = Path(path)
    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        return {}

    pipeline_section = raw.get("pipeline", {})
    if not isinstance(pipeline_section, dict):
        return {}

    # Allow env var overrides for pipeline fields
    env_overrides = {
        "INPUT_FILE": "input_file",
        "OUTPUT_FILE": "output_file",
        "BATCH_SIZE": "batch_size",
        "COLLECT_MEDIA": "collect_media",
        "COLLECT_SPECS": "collect_specs",
        "FOCUS_AREAS": "focus_areas",
        "MAX_ITERATIONS": "max_iterations",
    }
    for env_key, yaml_key in env_overrides.items():
        env_val = os.environ.get(env_key)
        if env_val is not None:
            pipeline_section[yaml_key] = env_val

    return pipeline_section
