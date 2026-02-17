"""
EU regulatory RSS feed adapter — Official Journal and MDCG publications.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import feedparser

from regkb.intelligence.fetcher import FetchResult, NewsletterEntry
from regkb.intelligence.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

# EU regulatory RSS feeds relevant to medical devices
EU_FEEDS = {
    "official_journal": "https://eur-lex.europa.eu/rss/cellar_legal_acts.xml",
    "mdcg": "https://health.ec.europa.eu/rss_en",
}


class EUOfficialJournalAdapter(SourceAdapter):
    """Fetch regulatory updates from EU Official Journal and health RSS feeds."""

    @property
    def name(self) -> str:
        return "EU Official Journal"

    @property
    def source_id(self) -> str:
        return "eu_oj"

    def fetch(self, days: int = 7) -> FetchResult:
        cutoff = datetime.now() - timedelta(days=days)
        entries = []
        errors = []

        for feed_name, feed_url in EU_FEEDS.items():
            try:
                feed_entries = self._parse_feed(feed_url, feed_name, cutoff)
                entries.extend(feed_entries)
            except Exception as e:
                logger.error("EU %s feed failed: %s", feed_name, e)
                errors.append(f"EU {feed_name}: {e}")

        # Filter to medical device relevance
        device_entries = self._filter_device_relevant(entries)

        return FetchResult(
            total_entries=len(device_entries),
            entries=device_entries,
            sources_fetched=len(EU_FEEDS),
            errors=errors,
            fetch_time=datetime.now(),
        )

    def _parse_feed(self, url: str, category: str, cutoff: datetime) -> list[NewsletterEntry]:
        """Parse a single RSS/Atom feed and return entries after cutoff."""
        feed = feedparser.parse(url)
        entries = []

        for item in feed.entries:
            published = self._parse_date(item)
            if published and published < cutoff:
                continue

            entry = NewsletterEntry(
                date=published.strftime("%Y-%m-%d") if published else "",
                agency="EU",
                category=f"EU - {category.replace('_', ' ').title()}",
                title=item.get("title", "").strip(),
                link=item.get("link"),
                date_parsed=published,
            )
            entries.append(entry)

        return entries

    def _filter_device_relevant(self, entries: list[NewsletterEntry]) -> list[NewsletterEntry]:
        """Filter entries to those relevant to medical devices."""
        device_keywords = [
            "medical device",
            "in vitro diagnostic",
            "2017/745",
            "2017/746",
            "MDR",
            "IVDR",
            "MDCG",
            "notified body",
            "CE mark",
            "EUDAMED",
            "UDI",
        ]
        relevant = []
        for entry in entries:
            title_lower = entry.title.lower()
            if any(kw.lower() in title_lower for kw in device_keywords):
                relevant.append(entry)
        return relevant

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
