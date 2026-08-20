"""Focus area configuration - domains, query modifiers, and source scoring."""

from __future__ import annotations

from enum import Enum


class FocusArea(str, Enum):
    """Supported research focus areas."""

    PRODUCT_PAGES = "product_pages"
    SELLER_IMAGES = "seller_images"
    YOUTUBE = "youtube"
    PRICE_COMPARISON = "price_comparison"
    SPECS = "specs"


# Domains associated with each focus area
FOCUS_DOMAINS: dict[FocusArea, list[str]] = {
    FocusArea.PRODUCT_PAGES: [
        "amazon.com",
        "bestbuy.com",
        "walmart.com",
        "target.com",
        "costco.com",
        "newegg.com",
        "bhphotovideo.com",
    ],
    FocusArea.SELLER_IMAGES: [
        "amazon.com",
        "ebay.com",
        "walmart.com",
        "bestbuy.com",
        "newegg.com",
        "aliexpress.com",
    ],
    FocusArea.YOUTUBE: [
        "youtube.com",
        "youtu.be",
    ],
    FocusArea.PRICE_COMPARISON: [
        "camelcamelcamel.com",
        "pcpartpicker.com",
        "pricespy.co.uk",
        "google.com/shopping",
        "pricegrabber.com",
    ],
    FocusArea.SPECS: [
        "gsmarena.com",
        "versus.com",
        "nanoreview.net",
        "notebookcheck.net",
        "technical.city",
        "devicespecifications.com",
    ],
}

# Query modifiers appended based on focus area
FOCUS_QUERY_MODIFIERS: dict[FocusArea, list[str]] = {
    FocusArea.PRODUCT_PAGES: ["buy", "shop"],
    FocusArea.SELLER_IMAGES: ["product images", "photos"],
    FocusArea.YOUTUBE: ["review", "unboxing", "hands on"],
    FocusArea.PRICE_COMPARISON: ["price", "deal", "compare prices"],
    FocusArea.SPECS: ["specifications", "specs", "datasheet"],
}

# Source priority scores (higher = more trusted)
FOCUS_SOURCE_SCORES: dict[FocusArea, float] = {
    FocusArea.PRODUCT_PAGES: 0.9,
    FocusArea.SELLER_IMAGES: 0.8,
    FocusArea.YOUTUBE: 0.7,
    FocusArea.PRICE_COMPARISON: 0.6,
    FocusArea.SPECS: 0.95,
}


class FocusConfig:
    """Configuration for focused research."""

    def __init__(self, areas: list[str | FocusArea] | None = None):
        self.areas = [FocusArea(a) if isinstance(a, str) else a for a in (areas or [])]

    @property
    def domains(self) -> list[str]:
        """Get all allowed domains across active focus areas."""
        result = []
        for area in self.areas:
            result.extend(FOCUS_DOMAINS.get(area, []))
        return list(dict.fromkeys(result))  # dedupe preserving order

    def get_modifiers(self, area: FocusArea) -> list[str]:
        """Get query modifiers for a specific focus area."""
        return FOCUS_QUERY_MODIFIERS.get(area, [])

    def score_url(self, url: str) -> float:
        """Score a URL based on how well it matches focus areas."""
        if not self.areas:
            return 0.5  # no focus = neutral score

        url_lower = url.lower()
        best_score = 0.0

        for area in self.areas:
            domains = FOCUS_DOMAINS.get(area, [])
            base_score = FOCUS_SOURCE_SCORES.get(area, 0.5)

            for domain in domains:
                if domain in url_lower:
                    best_score = max(best_score, base_score)

        return best_score

    def is_domain_allowed(self, url: str) -> bool:
        """Check if a URL's domain is in any active focus area."""
        if not self.areas:
            return True  # no focus = allow all

        url_lower = url.lower()
        for area in self.areas:
            for domain in FOCUS_DOMAINS.get(area, []):
                if domain in url_lower:
                    return True
        return False

    def to_dict(self) -> dict:
        """Serialize for state storage."""
        return {"areas": [a.value for a in self.areas]}

    @classmethod
    def from_dict(cls, data: dict) -> FocusConfig:
        """Deserialize from state storage."""
        return cls(areas=data.get("areas", []))


def parse_focus_areas(raw: str | list[str] | None) -> list[FocusArea]:
    """Parse focus areas from various input formats.

    Args:
        raw: Comma-separated string, list of strings, or None.

    Returns:
        List of valid FocusArea enums.
    """
    if not raw:
        return []

    if isinstance(raw, str):
        items = [s.strip() for s in raw.split(",") if s.strip()]
    else:
        items = raw

    valid = []
    for item in items:
        try:
            valid.append(FocusArea(item))
        except ValueError:
            pass  # skip invalid focus areas silently

    return valid


def get_focus_config(raw: str | list[str] | None = None) -> FocusConfig:
    """Create a FocusConfig from raw input."""
    areas = parse_focus_areas(raw)
    return FocusConfig(areas=areas)
