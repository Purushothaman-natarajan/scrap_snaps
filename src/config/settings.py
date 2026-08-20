"""Pydantic Settings for centralized configuration management."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings - flat env vars from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Azure OpenAI ===
    azure_api_key: str = Field(default="")
    azure_endpoint: str = Field(default="")
    azure_deployment: str = Field(default="")
    azure_consumer_id: str = Field(default="")
    llm_temperature: float = Field(default=0.0)
    llm_max_retries: int = Field(default=3)
    llm_timeout: float = Field(default=60.0)

    # === SerpAPI ===
    serpapi_key: str = Field(default="")

    # === Database ===
    database_url: str = Field(default="sqlite:///research.db")
    db_echo: bool = Field(default=False)
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)

    # === Execution ===
    max_iterations: int = Field(default=15)
    recursion_limit: int = Field(default=200)
    required_views: str = Field(default="front,back,left,right,top")

    # === Focus ===
    focus_areas: str = Field(default="product_pages,seller_images,youtube,specs")
    collect_specs: bool = Field(default=True)
    collect_media: str = Field(default="both")
    #   images      - image search + download + classify only
    #   videos      - full video pipeline (download → extract → classify → AI select)
    #   video_urls  - YouTube search only, return URLs, no download
    #   video_frames - download + extract frames + classify, skip AI frame selection
    #   both        - images + videos (full pipeline)
    #   none        - no media collection, specs only

    # === Networking ===
    rate_limit_interval: float = Field(default=1.0)
    request_timeout: float = Field(default=10.0)
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    )

    # === Playwright ===
    playwright_nav_timeout: int = Field(default=30000)
    playwright_selector_timeout: int = Field(default=10000)
    playwright_headless: bool = Field(default=True)

    # === Scraping ===
    download_dir: str = Field(default="downloads")
    max_image_results: int = Field(default=5)
    page_text_limit: int = Field(default=5000)
    max_download_size: int = Field(default=10485760)

    # === Image Extraction ===
    image_batch_size: int = Field(default=5)
    image_download_limit: int = Field(default=2)
    image_crop_ratio: float = Field(default=0.7)
    image_analyze_cache_ttl: float = Field(default=3600.0)

    # === Video Extraction ===
    video_download_dir: str = Field(default="downloads/videos")
    max_video_results: int = Field(default=2)
    video_min_duration: int = Field(default=180)
    video_max_duration: int = Field(default=900)
    video_frame_interval: float = Field(default=5.0)
    video_max_resolution: int = Field(default=480)
    crop_video_frames: bool = Field(default=False)
    ai_frame_selection: bool = Field(default=True)
    video_scene_threshold: float = Field(default=27.0)
    video_frame_jpeg_quality: int = Field(default=85)
    video_max_frames_per_view: int = Field(default=2)
    video_ai_selection_max_frames: int = Field(default=12)

    # === Perceptual Hashing ===
    phash_similarity_threshold: int = Field(default=10)

    # === Coverage / Termination ===
    coverage_max_cycles: int = Field(default=10)
    coverage_no_progress_threshold: int = Field(default=1)
    coverage_proximity_ratio: float = Field(default=0.8)

    # === Search Query Building ===
    search_domains_per_area: int = Field(default=2)
    search_modifiers_per_area: int = Field(default=2)
    search_queries_per_task: int = Field(default=2)

    # === Verification Scoring ===
    verify_weight_identity: float = Field(default=0.30)
    verify_weight_evidence: float = Field(default=0.25)
    verify_weight_image: float = Field(default=0.30)
    verify_weight_base: float = Field(default=0.15)

    # === Logging ===
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False)
    log_timestamp: bool = Field(default=True)
    log_capture: bool = Field(default=True)
    log_file: str = Field(default="logs/scrap_snaps.log")

    # === Search Cache ===
    search_cache_size: int = Field(default=500)
    serpapi_max_hits_per_row: int = Field(default=20)

    # === Failed URL Tracking ===
    failed_url_ttl: float = Field(default=300.0)

    @property
    def required_views_list(self) -> list[str]:
        return [v.strip() for v in self.required_views.split(",")]

    @property
    def weights(self) -> dict[str, float]:
        return {
            "identity": self.verify_weight_identity,
            "evidence": self.verify_weight_evidence,
            "image": self.verify_weight_image,
            "base": self.verify_weight_base,
        }

    def validate_required(self) -> list[str]:
        """Validate required settings are present. Returns list of missing keys."""
        missing = []
        if not self.azure_api_key:
            missing.append("AZURE_API_KEY")
        if not self.azure_endpoint:
            missing.append("AZURE_ENDPOINT")
        if not self.azure_deployment:
            missing.append("AZURE_DEPLOYMENT")
        return missing


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
