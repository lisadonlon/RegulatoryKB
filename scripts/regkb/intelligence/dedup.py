"""
Cross-source deduplication for regulatory intelligence entries.

Deduplicates by URL normalization and title similarity.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from regkb.intelligence.fetcher import NewsletterEntry

logger = logging.getLogger(__name__)

# Similarity threshold for title-based dedup
TITLE_SIMILARITY_THRESHOLD = 0.85


def normalize_url(url: Optional[str]) -> Optional[str]:
    """Normalize a URL for dedup comparison.

    Strips tracking params, trailing slashes, and normalizes case.
    """
    if not url:
        return None

    try:
        parsed = urlparse(url.lower().strip())

        # Remove common tracking parameters
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "ref",
            "source",
        }
        if parsed.query:
            params = parse_qs(parsed.query)
            filtered = {k: v for k, v in params.items() if k.lower() not in tracking_params}
            query = urlencode(filtered, doseq=True)
        else:
            query = ""

        # Remove trailing slash
        path = parsed.path.rstrip("/")

        return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, query, ""))
    except Exception:
        return url


def normalize_title(title: str) -> str:
    """Normalize a title for comparison — lowercase, strip punctuation, collapse whitespace."""
    if not title:
        return ""
    text = title.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def titles_similar(title1: str, title2: str) -> bool:
    """Check if two titles are similar enough to be duplicates."""
    n1 = normalize_title(title1)
    n2 = normalize_title(title2)
    if not n1 or not n2:
        return False
    return SequenceMatcher(None, n1, n2).ratio() >= TITLE_SIMILARITY_THRESHOLD


def deduplicate_entries(entries: list[NewsletterEntry]) -> list[NewsletterEntry]:
    """Remove duplicate entries based on URL and title similarity.

    Prefers entries with links over those without.
    When both have links, the first occurrence wins.
    """
    if not entries:
        return []

    # Sort so entries with links come first
    sorted_entries = sorted(entries, key=lambda e: (e.link is None, 0))

    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    unique: list[NewsletterEntry] = []

    for entry in sorted_entries:
        # Check URL dedup
        norm_url = normalize_url(entry.link)
        if norm_url and norm_url in seen_urls:
            continue

        # Check title dedup
        if any(titles_similar(entry.title, seen) for seen in seen_titles):
            continue

        # New unique entry
        if norm_url:
            seen_urls.add(norm_url)
        seen_titles.append(entry.title)
        unique.append(entry)

    dedup_count = len(entries) - len(unique)
    if dedup_count > 0:
        logger.info(
            "Deduplicated %d entries (from %d to %d)", dedup_count, len(entries), len(unique)
        )

    return unique
