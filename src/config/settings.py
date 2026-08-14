"""Pydantic Settings for centralized configuration management."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_", env_nested_delimiter="__")

    # Azure OpenAI (primary)
    azure_api_key: str = Field(default="", alias="AZURE_API_KEY")
    azure_endpoint: str = Field(default="", alias="AZURE_ENDPOINT")
    azure_deployment: str = Field(default="", alias="AZURE_DEPLOYMENT")
    azure_consumer_id: str = Field(default="", alias="AZURE_CONSUMER_ID")

    # Google GenAI (fallback)
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    google_model: str = Field(default="gemini-1.5-pro-latest", alias="LLM_MODEL")

    # Provider selection
    provider: Literal["azure", "google"] = Field(default="azure", alias="LLM_PROVIDER")

    # Common
    temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    timeout: float = Field(default=60.0, alias="LLM_TIMEOUT")


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_", env_nested_delimiter="__")

    url: str = Field(default="sqlite:///research.db", alias="DATABASE_URL")
    echo: bool = Field(default=False, alias="DB_ECHO")
    pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")


class ExecutionConfig(BaseSettings):
    """Execution/agent runtime configuration."""

    model_config = SettingsConfigDict(env_prefix="EXEC_", env_nested_delimiter="__")

    max_iterations: int = Field(default=30, alias="MAX_ITERATIONS")
    recursion_limit: int = Field(default=50, alias="RECURSION_LIMIT")
    required_views: str = Field(default="front,back,side,top", alias="REQUIRED_VIEWS")

    @property
    def required_views_list(self) -> list[str]:
        return [v.strip() for v in self.required_views.split(",")]


class NetworkConfig(BaseSettings):
    """Networking and HTTP configuration."""

    model_config = SettingsConfigDict(env_prefix="NET_", env_nested_delimiter="__")

    rate_limit_interval: float = Field(default=1.0, alias="RATE_LIMIT_INTERVAL")
    request_timeout: float = Field(default=10.0, alias="REQUEST_TIMEOUT")
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        alias="USER_AGENT",
    )


class PlaywrightConfig(BaseSettings):
    """Playwright browser automation configuration."""

    model_config = SettingsConfigDict(env_prefix="PW_", env_nested_delimiter="__")

    nav_timeout: int = Field(default=30000, alias="PLAYWRIGHT_NAV_TIMEOUT")
    selector_timeout: int = Field(default=10000, alias="PLAYWRIGHT_SELECTOR_TIMEOUT")
    headless: bool = Field(default=True, alias="PLAYWRIGHT_HEADLESS")


class ScrapingConfig(BaseSettings):
    """Web scraping configuration."""

    model_config = SettingsConfigDict(env_prefix="SCRAPE_", env_nested_delimiter="__")

    download_dir: str = Field(default="downloads", alias="DOWNLOAD_DIR")
    max_image_results: int = Field(default=5, alias="MAX_IMAGE_RESULTS")
    page_text_limit: int = Field(default=5000, alias="PAGE_TEXT_LIMIT")
    max_download_size: int = Field(default=10485760, alias="MAX_DOWNLOAD_SIZE")


class VideoConfig(BaseSettings):
    """Video extraction configuration."""

    model_config = SettingsConfigDict(env_prefix="VIDEO_", env_nested_delimiter="__")

    download_dir: str = Field(default="downloads/videos", alias="VIDEO_DOWNLOAD_DIR")
    max_results: int = Field(default=2, alias="MAX_VIDEO_RESULTS")
    min_duration: int = Field(default=180, alias="VIDEO_MIN_DURATION")
    max_duration: int = Field(default=900, alias="VIDEO_MAX_DURATION")
    frame_interval: float = Field(default=2.0, alias="VIDEO_FRAME_INTERVAL")
    max_resolution: int = Field(default=720, alias="VIDEO_MAX_RESOLUTION")
    ai_frame_selection: bool = Field(default=True, alias="AI_FRAME_SELECTION")


class VerificationConfig(BaseSettings):
    """Verification scoring weights configuration."""

    model_config = SettingsConfigDict(env_prefix="VERIFY_", env_nested_delimiter="__")

    weight_identity: float = Field(default=0.30, alias="VERIFY_WEIGHT_IDENTITY")
    weight_evidence: float = Field(default=0.25, alias="VERIFY_WEIGHT_EVIDENCE")
    weight_image: float = Field(default=0.30, alias="VERIFY_WEIGHT_IMAGE")
    weight_base: float = Field(default=0.15, alias="VERIFY_WEIGHT_BASE")

    @property
    def weights(self) -> dict[str, float]:
        return {
            "identity": self.weight_identity,
            "evidence": self.weight_evidence,
            "image": self.weight_image,
            "base": self.weight_base,
        }


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(env_prefix="LOG_", env_nested_delimiter="__")

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    json_format: bool = Field(default=False, alias="LOG_JSON")
    include_timestamp: bool = Field(default=True, alias="LOG_TIMESTAMP")


class Settings(BaseSettings):
    """Main application settings - composes all sub-configs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    playwright: PlaywrightConfig = Field(default_factory=PlaywrightConfig)
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def validate_required(self) -> list[str]:
        """Validate required settings are present. Returns list of missing keys."""
        missing = []
        if self.llm.provider == "azure":
            if not self.llm.azure_api_key:
                missing.append("AZURE_API_KEY")
            if not self.llm.azure_endpoint:
                missing.append("AZURE_ENDPOINT")
            if not self.llm.azure_deployment:
                missing.append("AZURE_DEPLOYMENT")
        else:
            if not self.llm.google_api_key:
                missing.append("GOOGLE_API_KEY")
        return missing


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
