"""Page fetching tools — static HTTP and JS-rendered pages.

Provides LangChain tools:
  - fetch_page: static HTTP fetch with retry and rate limiting
  - fetch_page_js: Playwright-based fetch for JS-rendered pages
  - extract_structured_data: parse HTML tables, lists, metadata

Playwright headless mode is configurable via PLAYWRIGHT_HEADLESS.
"""

from bs4 import BeautifulSoup
from langchain_core.tools import tool

from src.config import (
    PAGE_TEXT_LIMIT,
    PLAYWRIGHT_HEADLESS,
    PLAYWRIGHT_NAV_TIMEOUT,
    PLAYWRIGHT_SELECTOR_TIMEOUT,
    USER_AGENT,
)
from src.config.logging import get_logger
from src.tools.logging import log_tool_call
from src.tools.utils.http import can_fetch, http_get

logger = get_logger(__name__)


@tool
@log_tool_call
def fetch_page(url: str) -> str:
    """Fetch the text content of a static web page."""
    logger.info("Fetching page: %s", url)

    if not can_fetch(url):
        return f"Blocked by robots.txt: {url}"

    try:
        response = http_get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.extract()

        text = soup.get_text(separator=" ", strip=True)
        return text[:PAGE_TEXT_LIMIT]
    except Exception as e:
        return f"Error fetching {url}: {e}"


@tool
@log_tool_call
def fetch_page_js(url: str, wait_selector: str = "body") -> str:
    """Fetch page content using Playwright for JS-rendered pages.

    Use this for e-commerce sites (Amazon, Walmart, etc.) that render via JavaScript.
    Requires: playwright install chromium
    """
    logger.info("Fetching JS-rendered page: %s", url)

    if not can_fetch(url):
        return f"Blocked by robots.txt: {url}"

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
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
        logger.error("Playwright not installed. Run: playwright install chromium")
        return fetch_page.invoke({"url": url})
    except Exception as e:
        logger.error("JS fetch failed for %s: %s, falling back to static", url, e)
        return fetch_page.invoke({"url": url})


@tool
@log_tool_call
def extract_structured_data(url: str) -> dict:
    """Extract structured data (tables, lists, specs) from a web page.

    Returns a dict with 'tables', 'lists', and 'meta' keys.
    """
    logger.info("Extracting structured data from: %s", url)

    if not can_fetch(url):
        return {"error": "Blocked by robots.txt", "tables": [], "lists": [], "meta": {}}

    try:
        response = http_get(url)
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
