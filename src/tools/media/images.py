"""Image tools - download, analyze, deduplicate."""

import base64
import hashlib
import json
import os

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from src.config import DOWNLOAD_DIR, MAX_DOWNLOAD_SIZE
from src.config.logging import get_logger
from src.llm import get_vision_llm
from src.tools.utils.hashing import perceptual_hash
from src.tools.utils.http import http_get

logger = get_logger(__name__)


@tool
def download_image(url: str, save_dir: str = DOWNLOAD_DIR) -> str:
    """Download an image from a URL and return its local path."""
    os.makedirs(save_dir, exist_ok=True)

    filename = url.split("/")[-1].split("?")[0]
    if not filename or "." not in filename:
        ext = ".jpg"
        filename = f"image_{hashlib.md5(url.encode()).hexdigest()}{ext}"

    local_path = os.path.join(save_dir, filename)

    if os.path.exists(local_path):
        return local_path

    try:
        response = http_get(url)

        content_length = int(response.headers.get("content-length", "0"))
        if content_length > MAX_DOWNLOAD_SIZE:
            logger.warning("Image too large (%d bytes): %s", content_length, url)
            return ""

        content_type = response.headers.get("content-type", "")
        if "image" not in content_type and not url.lower().endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".webp")
        ):
            logger.warning(
                "URL does not appear to be an image: %s (content-type: %s)", url, content_type
            )

        with open(local_path, "wb") as f:
            f.write(response.content)
        return local_path
    except Exception as e:
        logger.error("Error downloading %s: %s", url, e)
        return ""


@tool
def analyze_image(image_path: str) -> dict:
    """Analyze an image using a vision model to determine the view type."""
    if not os.path.exists(image_path):
        return {"product_match": False, "view": "unknown", "confidence": 0.0}

    try:
        llm = get_vision_llm()

        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        prompt = (
            "Analyze this product image. Determine the primary view of the product "
            "from this list: [front, back, left, right, top, bottom, detail, unknown]. "
            "Is it clearly a product image (not a person or generic scene)?\n\n"
            "Reply strictly in this JSON format:\n"
            '{"product_match": true/false, "view": "one_of_the_options", '
            '"confidence": 0.0_to_1.0}'
        )

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
            ]
        )

        response = llm.invoke([message])

        text = response.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)

        required_keys = {"product_match", "view", "confidence"}
        if not required_keys.issubset(data.keys()):
            logger.warning("LLM response missing required keys: %s", data)
            return {"product_match": False, "view": "unknown", "confidence": 0.0}

        return data
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON response for %s: %s", image_path, e)
        return {"product_match": False, "view": "unknown", "confidence": 0.0}
    except Exception as e:
        logger.error("Error analyzing image %s: %s", image_path, e)
        return {"product_match": False, "view": "unknown", "confidence": 0.0}


@tool
def deduplicate_images(image_paths: list[str]) -> list[str]:
    """Take a list of image paths and return paths of unique images based on pHash."""
    unique_paths = []
    seen_hashes: set = set()
    for path in image_paths:
        if not path or not os.path.exists(path):
            continue

        h = perceptual_hash(path)
        if h is not None and h not in seen_hashes:
            seen_hashes.add(h)
            unique_paths.append(path)
    return unique_paths
