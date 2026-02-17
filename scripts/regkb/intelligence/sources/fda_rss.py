"""
FDA CDRH RSS feed adapter — device guidance, recalls, and safety communications.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import feedparser

from regkb.intelligence.fetcher import FetchResult, NewsletterEntry
from regkb.intelligence.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

# FDA CDRH RSS feeds (medical devices)
FDA_FEEDS = {
    "guidance": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/cdrh-guidance-documents/rss.xml",
    "recalls": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medical-device-recalls/rss.xml",
    "safety": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medical-device-safety/rss.xml",
}


class FDACDRHAdapter(SourceAdapter):
    """Fetch regulatory updates from FDA CDRH RSS feeds."""

    @property
    def name(self) -> str:
        return "FDA CDRH"

    @property
    def source_id(self) -> str:
        return "fda_cdrh"

    def fetch(self, days: int = 7) -> FetchResult:
        cutoff = datetime.now() - timedelta(days=days)
        entries = []
        errors = []

        for feed_name, feed_url in FDA_FEEDS.items():
            try:
                feed_entries = self._parse_feed(feed_url, feed_name, cutoff)
                entries.extend(feed_entries)
            except Exception as e:
                logger.error("FDA %s feed failed: %s", feed_name, e)
                errors.append(f"FDA {feed_name}: {e}")

        return FetchResult(
            total_entries=len(entries),
            entries=entries,
            sources_fetched=len(FDA_FEEDS),
            errors=errors,
            fetch_time=datetime.now(),
        )

    def _parse_feed(self, url: str, category: str, cutoff: datetime) -> list[NewsletterEntry]:
        """Parse a single RSS feed and return entries after cutoff."""
        feed = feedparser.parse(url)
        entries = []

        for item in feed.entries:
            published = self._parse_date(item)
            if published and published < cutoff:
                continue

            entry = NewsletterEntry(
                date=published.strftime("%Y-%m-%d") if published else "",
                agency="FDA",
                category=f"Medical Devices - {category.title()}",
                title=item.get("title", "").strip(),
                link=item.get("link"),
                date_parsed=published,
            )
            entries.append(entry)

        return entries

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
