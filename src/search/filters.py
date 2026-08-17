"""Search result filtering, scoring, and deduplication."""

from __future__ import annotations

from urllib.parse import urlparse

from src.search.focus import FocusConfig


def filter_results(
    results: list[dict],
    focus: FocusConfig | None = None,
) -> list[dict]:
    """Filter search results by focus area domains.

    Args:
        results: List of search result dicts with 'url' key.
        focus: Focus config to filter by. If None or no areas, returns all.

    Returns:
        Filtered results matching focus domains.
    """
    if not focus or not focus.areas:
        return results

    allowed = []
    for r in results:
        url = r.get("url", "")
        if focus.is_domain_allowed(url):
            allowed.append(r)

    return allowed


def score_source(url: str, focus: FocusConfig | None = None) -> float:
    """Score a URL based on source trustworthiness and focus alignment.

    Args:
        url: The URL to score.
        focus: Focus config for domain-based scoring.

    Returns:
        Score from 0.0 (low) to 1.0 (high).
    """
    score = 0.5  # base score

    if not url:
        return 0.0

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Boost for known high-quality domains
    high_quality = [
        "amazon.com",
        "bestbuy.com",
        "walmart.com",
        "manufacturer websites",
        "gsmarena.com",
        "youtube.com",
    ]

    for hq in high_quality:
        if hq in domain:
            score += 0.2
            break

    # Apply focus-based scoring
    if focus:
        focus_score = focus.score_url(url)
        if focus_score > 0:
            score = max(score, focus_score)

    return min(score, 1.0)


def deduplicate_domains(results: list[dict]) -> list[dict]:
    """Keep only the best result from each domain.

    Assumes results are already sorted by relevance.
    """
    seen_domains: dict[str, dict] = {}

    for r in results:
        url = r.get("url", "")
        if not url:
            continue

        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            continue

        if domain not in seen_domains:
            seen_domains[domain] = r

    return list(seen_domains.values())


def sort_by_focus(
    results: list[dict],
    focus: FocusConfig | None = None,
) -> list[dict]:
    """Sort results by focus relevance.

    Results matching focus areas are boosted to the top.
    """
    if not focus or not focus.areas:
        return results

    def sort_key(r: dict) -> float:
        url = r.get("url", "")
        return -focus.score_url(url)  # negative for descending

    return sorted(results, key=sort_key)
