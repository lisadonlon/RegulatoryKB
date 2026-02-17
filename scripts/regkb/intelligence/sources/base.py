"""
Base class for regulatory intelligence source adapters.
"""

from abc import ABC, abstractmethod

from regkb.intelligence.fetcher import FetchResult


class SourceAdapter(ABC):
    """Abstract base class for regulatory update sources.

    Each adapter fetches updates from a single source and returns
    a standard FetchResult with NewsletterEntry items.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable source name."""
        ...

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this source (used in dedup)."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether this source is enabled. Override to check config."""
        return True

    @abstractmethod
    def fetch(self, days: int = 7) -> FetchResult:
        """Fetch regulatory updates from this source.

        Args:
            days: Number of days to look back.

        Returns:
            FetchResult with entries and metadata.
        """
        ...
