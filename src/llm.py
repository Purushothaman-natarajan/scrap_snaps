"""LLM client configuration - Corporate Azure/OpenAI-compatible gateway."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.config.logging import get_logger
from src.config.settings import settings

logger = get_logger(__name__)


@lru_cache(maxsize=4)
def _get_azure_llm(temperature: float = 0.0) -> ChatOpenAI:
    """Create and cache LLM instance for the corporate OpenAI-compatible gateway."""

    endpoint = settings.azure_endpoint.rstrip("/")
    deployment = settings.azure_deployment
    consumer_id = settings.azure_consumer_id.strip()

    # Your corporate gateway does not use a normal Azure API key.
    # It authenticates through the corporate endpoint + consumer header.
    #
    # openai-python requires a non-empty api_key during client creation,
    # so "nokey" is intentionally used as a placeholder.
    api_key = "nokey"

    if not endpoint:
        raise ValueError("AZURE_ENDPOINT is missing")

    if not deployment:
        raise ValueError("AZURE_DEPLOYMENT is missing")

    if not consumer_id:
        raise ValueError("AZURE_CONSUMER_ID is missing")

    base_url = endpoint

    # IMPORTANT:
    #
    # Your corporate gateway accepted the request when BOTH spellings
    # were supplied:
    #
    #   x_niq_cis_consumer
    #   x-niq-cis-consumer
    #
    # The test with only x_niq_cis_consumer returned:
    #
    #   Field required: header.x_niq_cis_consumer
    #
    # The test with both headers returned HTTP 200.
    headers = {
        "x_niq_cis_consumer": consumer_id,
        "x-niq-cis-consumer": consumer_id,
    }

    logger.info(
        "Initializing corporate Azure LLM: deployment=%s, "
        "temperature=%s, base_url=%s, consumer_id_present=%s",
        deployment,
        temperature,
        base_url,
        bool(consumer_id),
    )

    return ChatOpenAI(
        model=deployment,
        api_key=api_key,
        base_url=base_url,
        default_headers=headers,
        temperature=temperature,
        max_retries=settings.llm_max_retries,
        timeout=settings.llm_timeout,
    )


def get_llm(temperature: float = 0.0) -> BaseChatModel:
    """Return the corporate Azure/OpenAI-compatible LLM."""
    return _get_azure_llm(temperature)


def get_vision_llm(temperature: float = 0.0) -> BaseChatModel:
    """Return the vision-capable corporate LLM."""
    return get_llm(temperature)


def clear_llm_cache() -> None:
    """Clear cached LLM instances."""
    _get_azure_llm.cache_clear()
