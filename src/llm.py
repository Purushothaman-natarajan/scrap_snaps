"""LLM client configuration - Azure OpenAI provider."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.config.logging import get_logger
from src.config.settings import settings

logger = get_logger(__name__)


@lru_cache(maxsize=4)
def _get_azure_llm(temperature: float) -> ChatOpenAI:
    """Create and cache Azure OpenAI LLM instance."""
    llm_config = settings.llm

    if not llm_config.azure_api_key or llm_config.azure_api_key == "your_azure_api_key_here":
        logger.warning("AZURE_API_KEY is missing or invalid. LLM calls will fail.")

    if not llm_config.azure_endpoint:
        logger.warning("AZURE_ENDPOINT is missing. LLM calls will fail.")

    if not llm_config.azure_deployment:
        logger.warning("AZURE_DEPLOYMENT is missing. LLM calls will fail.")

    if not llm_config.azure_consumer_id:
        logger.warning("AZURE_CONSUMER_ID is missing. LLM calls may fail.")

    return ChatOpenAI(
        model=llm_config.azure_deployment,
        temperature=temperature,
        api_key=llm_config.azure_api_key,
        base_url=f"{llm_config.azure_endpoint.rstrip('/')}/openai/v1/",
        default_headers={
            "X-Consumer-ID": llm_config.azure_consumer_id,
        },
        max_retries=llm_config.max_retries,
        timeout=llm_config.timeout,
    )


def get_llm(temperature: float = 0.0) -> BaseChatModel:
    """Return an Azure OpenAI LLM instance.

    Args:
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        Configured LLM instance.
    """
    return _get_azure_llm(temperature)


def get_vision_llm(temperature: float = 0.0) -> BaseChatModel:
    """Return a vision-capable LLM instance.

    Uses the same Azure OpenAI model which supports vision.
    """
    return get_llm(temperature)


def clear_llm_cache() -> None:
    """Clear the LLM instance cache. Useful for testing or config changes."""
    _get_azure_llm.cache_clear()
