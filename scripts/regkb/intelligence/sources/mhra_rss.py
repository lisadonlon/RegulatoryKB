"""
MHRA (UK) RSS feed adapter — medical device guidance and safety alerts.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import feedparser

from regkb.intelligence.fetcher import FetchResult, NewsletterEntry
from regkb.intelligence.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

# MHRA/GOV.UK RSS feeds for medical devices
MHRA_FEEDS = {
    "alerts": "https://www.gov.uk/drug-device-alerts.atom",
    "guidance": "https://www.gov.uk/government/publications.atom?departments%5B%5D=medicines-and-healthcare-products-regulatory-agency&publication_filter_option=guidance",
}


class MHRAAdapter(SourceAdapter):
    """Fetch regulatory updates from MHRA/GOV.UK RSS feeds."""

    @property
    def name(self) -> str:
        return "MHRA (UK)"

    @property
    def source_id(self) -> str:
        return "mhra"

    def fetch(self, days: int = 7) -> FetchResult:
        cutoff = datetime.now() - timedelta(days=days)
        entries = []
        errors = []

        for feed_name, feed_url in MHRA_FEEDS.items():
            try:
                feed_entries = self._parse_feed(feed_url, feed_name, cutoff)
                entries.extend(feed_entries)
            except Exception as e:
                logger.error("MHRA %s feed failed: %s", feed_name, e)
                errors.append(f"MHRA {feed_name}: {e}")

        return FetchResult(
            total_entries=len(entries),
            entries=entries,
            sources_fetched=len(MHRA_FEEDS),
            errors=errors,
            fetch_time=datetime.now(),
        )

    def _parse_feed(self, url: str, category: str, cutoff: datetime) -> list[NewsletterEntry]:
        """Parse an Atom/RSS feed and return entries after cutoff."""
        feed = feedparser.parse(url)
        entries = []

        for item in feed.entries:
            published = self._parse_date(item)
            if published and published < cutoff:
                continue

            title = item.get("title", "").strip()

            # For alerts feed, filter to device-related alerts
            if category == "alerts" and not self._is_device_alert(title):
                continue

            entry = NewsletterEntry(
                date=published.strftime("%Y-%m-%d") if published else "",
                agency="MHRA",
                category=f"UK - {category.title()}",
                title=title,
                link=item.get("link"),
                date_parsed=published,
            )
            entries.append(entry)

        return entries

    def _is_device_alert(self, title: str) -> bool:
        """Check if an alert is device-related (vs drug-related)."""
        title_lower = title.lower()
        device_indicators = [
            "medical device",
            "mda/",
            "device alert",
            "all medical device",
        ]
        return any(indicator in title_lower for indicator in device_indicators)

    def _parse_date(self, item) -> Optional[datetime]:
        """Extract publication date from feed item."""
        if hasattr(item, "published_parsed") and item.published_parsed:
            try:
                from time import mktime

                return datetime.fromtimestamp(mktime(item.published_parsed))
            except (ValueError, OverflowError):
                pass

        if hasattr(item, "updated_parsed") and item.updated_parsed:
            try:
                from time import mktime

                return datetime.fromtimestamp(mktime(item.updated_parsed))
            except (ValueError, OverflowError):
                pass

        return None
