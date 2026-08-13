"""LLM client configuration."""

import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import GOOGLE_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.0):
    """Return an instance of the Gemini LLM.

    Requires GOOGLE_API_KEY to be set in the environment.
    """
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "your_google_api_key_here":
        logger.warning("GOOGLE_API_KEY is missing or invalid. LLM calls will fail.")

    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        temperature=temperature,
        google_api_key=GOOGLE_API_KEY,
    )


def get_vision_llm(temperature: float = 0.0):
    """Return an instance of the Gemini Vision LLM."""
    return get_llm(temperature)
