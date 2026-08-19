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
    max_iterations: int = Field(default=30)
    recursion_limit: int = Field(default=200)
    required_views: str = Field(default="front,back,side,top")

    # === Focus ===
    focus_areas: str = Field(default="product_pages,seller_images,youtube,specs")
    collect_specs: bool = Field(default=True)
    collect_media: str = Field(default="both")  # images, videos, or both

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

    # === Video Extraction ===
    video_download_dir: str = Field(default="downloads/videos")
    max_video_results: int = Field(default=2)
    video_min_duration: int = Field(default=180)
    video_max_duration: int = Field(default=900)
    video_frame_interval: float = Field(default=2.0)
    video_max_resolution: int = Field(default=720)
    ai_frame_selection: bool = Field(default=True)

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
