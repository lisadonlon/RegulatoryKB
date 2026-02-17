"""
Adapter wrapping the existing NewsletterFetcher as a SourceAdapter.
"""

from regkb.intelligence.fetcher import FetchResult, NewsletterFetcher
from regkb.intelligence.sources.base import SourceAdapter


class NewsletterSourceAdapter(SourceAdapter):
    """Wraps the existing Index-of-Indexes newsletter fetcher."""

    @property
    def name(self) -> str:
        return "Index-of-Indexes Newsletter"

    @property
    def source_id(self) -> str:
        return "ioi"

    def fetch(self, days: int = 7) -> FetchResult:
        fetcher = NewsletterFetcher()
        return fetcher.fetch(days=days)
