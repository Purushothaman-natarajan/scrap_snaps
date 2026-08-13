import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

def get_llm(temperature: float = 0.0):
    """
    Returns an instance of the Gemini LLM.
    Requires GOOGLE_API_KEY to be set in the environment.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your_google_api_key_here":
        # Fallback/mock for local testing without key
        print("WARNING: GOOGLE_API_KEY is missing or invalid. Calls to LLM will fail.")
        
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-pro-latest", # Recommended for vision and complex extraction
        temperature=temperature,
        google_api_key=api_key
    )

def get_vision_llm(temperature: float = 0.0):
    """
    Returns an instance of the Gemini Vision LLM.
    """
    return get_llm(temperature) # gemini-1.5-pro handles both text and vision
