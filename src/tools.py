"""Web scraping, search, and analysis tools for the research agent."""

import base64
import hashlib
import json
import logging
import os
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import imagehash
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from PIL import Image as PILImage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import (
    DATABASE_URL,
    DOWNLOAD_DIR,
    MAX_DOWNLOAD_SIZE,
    MAX_IMAGE_RESULTS,
    PAGE_TEXT_LIMIT,
    PLAYWRIGHT_NAV_TIMEOUT,
    PLAYWRIGHT_SELECTOR_TIMEOUT,
    RATE_LIMIT_INTERVAL,
    REQUEST_TIMEOUT,
    USER_AGENT,
)
from src.llm import get_vision_llm

logger = logging.getLogger(__name__)

_last_request_time = 0.0
_robot_parsers: dict[str, RobotFileParser] = {}


def _rate_limit():
    """Enforce minimum interval between requests."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < RATE_LIMIT_INTERVAL:
        time.sleep(RATE_LIMIT_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def _can_fetch(url: str, user_agent: str = "*") -> bool:
    """Check if a URL is allowed by robots.txt."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    if base_url not in _robot_parsers:
        rp = RobotFileParser()
        robots_url = f"{base_url}/robots.txt"
        try:
            rp.set_url(robots_url)
            rp.read()
            _robot_parsers[base_url] = rp
        except Exception:
            # Fail open: if robots.txt is unreachable or malformed, allow the request
            # rather than blocking all scraping. Most sites don't restrict research bots.
            logger.debug("Could not fetch robots.txt for %s, allowing", base_url)
            return True

    rp = _robot_parsers[base_url]
    can = rp.can_fetch(user_agent, url)
    if not can:
        logger.info("robots.txt disallows fetching: %s", url)
    return can


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)),
)
def _http_get(url: str, timeout: float = REQUEST_TIMEOUT) -> httpx.Response:
    """HTTP GET with retry, rate limiting, and User-Agent."""
    _rate_limit()
    response = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response


@tool
def search_web(query: str, limit: int = 10) -> list[dict]:
    """Search the web for a given query."""
    logger.info("Executing web search for: %s", query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=limit))
            return [{"url": r["href"], "title": r["title"], "snippet": r["body"]} for r in results]
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s, attempting fallback", e)
        try:
            # Fallback: scrape DuckDuckGo's HTML-only endpoint directly.
            # This bypasses the API library but works when the DDGS client is rate-limited.
            _rate_limit()
            resp = httpx.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            fallback_results = []
            for link in soup.select("a.result__a")[:limit]:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if href and title:
                    fallback_results.append({"url": href, "title": title, "snippet": ""})
            return fallback_results
        except Exception as fallback_error:
            logger.error("Search fallback also failed: %s", fallback_error)
            return []


@tool
def search_images(query: str, limit: int = MAX_IMAGE_RESULTS) -> list[dict]:
    """Search for images matching a query."""
    logger.info("Executing image search for: %s", query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=limit))
            return [
                {"url": r.get("image", ""), "title": r.get("title", "")}
                for r in results
                if r.get("image")
            ]
    except Exception as e:
        logger.error("Image search failed: %s", e)
        return []


@tool
def fetch_page(url: str) -> str:
    """Fetch the text content of a static web page."""
    logger.info("Fetching page: %s", url)

    if not _can_fetch(url):
        return f"Blocked by robots.txt: {url}"

    try:
        response = _http_get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.extract()

        text = soup.get_text(separator=" ", strip=True)
        return text[:PAGE_TEXT_LIMIT]
    except Exception as e:
        return f"Error fetching {url}: {e}"


@tool
def fetch_page_js(url: str, wait_selector: str = "body") -> str:
    """Fetch page content using Playwright for JS-rendered pages.

    Use this for e-commerce sites (Amazon, Walmart, etc.) that render via JavaScript.
    Requires: playwright install chromium
    """
    logger.info("Fetching JS-rendered page: %s", url)

    if not _can_fetch(url):
        return f"Blocked by robots.txt: {url}"

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright

        # Three-layer fallback: Playwright (JS) -> static fetch -> error.
        # Most e-commerce sites need JS rendering; static fetch is the safe fallback.
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_NAV_TIMEOUT)
                page.wait_for_selector(wait_selector, timeout=PLAYWRIGHT_SELECTOR_TIMEOUT)
            except PlaywrightTimeout as e:
                logger.warning("Playwright timeout for %s: %s", url, e)
                browser.close()
                return fetch_page.invoke({"url": url})

            content = page.content()
            browser.close()

        soup = BeautifulSoup(content, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.extract()

        text = soup.get_text(separator=" ", strip=True)
        return text[:PAGE_TEXT_LIMIT]
    except ImportError:
        # Playwright not installed - graceful degradation to static HTTP
        logger.error("Playwright not installed. Run: playwright install chromium")
        return fetch_page.invoke({"url": url})
    except Exception as e:
        # Any Playwright error (network, crash, etc.) falls back to static fetch
        logger.error("JS fetch failed for %s: %s, falling back to static", url, e)
        return fetch_page.invoke({"url": url})


@tool
def extract_structured_data(url: str) -> dict:
    """Extract structured data (tables, lists, specs) from a web page.

    Returns a dict with 'tables', 'lists', and 'meta' keys.
    """
    logger.info("Extracting structured data from: %s", url)

    if not _can_fetch(url):
        return {"error": "Blocked by robots.txt", "tables": [], "lists": [], "meta": {}}

    try:
        response = _http_get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style"]):
            tag.extract()

        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)

        lists = []
        for ul in soup.find_all(["ul", "ol"]):
            items = [li.get_text(strip=True) for li in ul.find_all("li")]
            if items:
                lists.append(items)

        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name") or tag.get("property", "")
            content = tag.get("content", "")
            if name and content:
                meta[name] = content

        return {"tables": tables[:10], "lists": lists[:10], "meta": meta}
    except Exception as e:
        return {"error": str(e), "tables": [], "lists": [], "meta": {}}


@tool
def download_image(url: str, save_dir: str = DOWNLOAD_DIR) -> str:
    """Download an image from a URL and return its local path."""
    os.makedirs(save_dir, exist_ok=True)

    filename = url.split("/")[-1].split("?")[0]
    if not filename or "." not in filename:
        # URL has no recognizable filename - generate one using MD5 hash
        # to ensure uniqueness across different URLs
        ext = ".jpg"
        filename = f"image_{hashlib.md5(url.encode()).hexdigest()}{ext}"

    local_path = os.path.join(save_dir, filename)

    if os.path.exists(local_path):
        return local_path

    try:
        response = _http_get(url)

        content_length = int(response.headers.get("content-length", "0"))
        if content_length > MAX_DOWNLOAD_SIZE:
            logger.warning("Image too large (%d bytes): %s", content_length, url)
            return ""

        content_type = response.headers.get("content-type", "")
        # Validate the response is actually an image. Some URLs redirect to
        # HTML error pages. Check both Content-Type header and file extension.
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
        # LLMs often wrap JSON in markdown code fences - strip them before parsing
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

        try:
            img = PILImage.open(path)
            # Perceptual hash (pHash) detects visually similar images even if
            # they differ in resolution, compression, or minor edits. This is
            # more robust than exact hashing (md5/sha) for image deduplication.
            h = imagehash.phash(img)
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_paths.append(path)
        except Exception as e:
            logger.warning("Error processing %s for deduplication: %s", path, e)
    return unique_paths


@tool
def check_robots(url: str) -> dict:
    """Check if a URL is allowed by robots.txt."""
    try:
        can = _can_fetch(url)
        return {"url": url, "allowed": can}
    except Exception as e:
        logger.error("Error checking robots.txt for %s: %s", url, e)
        return {"url": url, "allowed": True, "error": str(e)}


@tool
def save_evidence(claim: dict) -> str:
    """Save an evidence claim to the database."""
    from src.db import Claim as ClaimModel
    from src.db import init_db

    session = init_db(DATABASE_URL)

    try:
        db_claim = ClaimModel(
            product_id=claim.get("product_id"),
            source_id=claim.get("source_id"),
            claim_type=claim.get("claim", ""),
            value=claim.get("value", ""),
            confidence=claim.get("confidence", 0.0),
        )
        session.add(db_claim)
        session.commit()
        return f"Saved claim: {claim.get('claim')} = {claim.get('value')}"
    except Exception as e:
        session.rollback()
        logger.error("Failed to save evidence: %s", e)
        return f"Failed to save claim: {e}"
    finally:
        session.close()
