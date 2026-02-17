"""
Source registry — fetches from all enabled sources and deduplicates.
"""

import logging
from datetime import datetime

from regkb.intelligence.fetcher import FetchResult
from regkb.intelligence.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


def get_all_adapters() -> list[SourceAdapter]:
    """Get instances of all available source adapters."""
    adapters: list[SourceAdapter] = []

    # Always include the newsletter adapter
    from regkb.intelligence.sources.newsletter import NewsletterSourceAdapter

    adapters.append(NewsletterSourceAdapter())

    # Try to load optional RSS adapters
    _try_load(adapters, "regkb.intelligence.sources.fda_rss", "FDACDRHAdapter")
    _try_load(adapters, "regkb.intelligence.sources.eu_rss", "EUOfficialJournalAdapter")
    _try_load(adapters, "regkb.intelligence.sources.mhra_rss", "MHRAAdapter")

    return [a for a in adapters if a.enabled]


def _try_load(adapters: list, module_path: str, class_name: str) -> None:
    """Try to import and instantiate an adapter, skip if unavailable."""
    try:
        import importlib

        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        adapters.append(cls())
    except ImportError:
        logger.debug("Optional adapter %s not available (missing dependency)", class_name)
    except Exception:
        logger.warning("Failed to load adapter %s", class_name, exc_info=True)


def fetch_all_sources(days: int = 7) -> FetchResult:
    """Fetch from all enabled sources, merge, and deduplicate.

    Args:
        days: Number of days to look back.

    Returns:
        Merged FetchResult with deduplicated entries.
    """
    adapters = get_all_adapters()
    all_entries = []
    all_errors = []
    sources_fetched = 0

    for adapter in adapters:
        try:
            logger.info("Fetching from %s...", adapter.name)
            result = adapter.fetch(days=days)
            all_entries.extend(result.entries)
            all_errors.extend(result.errors)
            sources_fetched += 1
            logger.info("  %s: %d entries", adapter.name, len(result.entries))
        except Exception as e:
            logger.error("Source %s failed: %s", adapter.name, e)
            all_errors.append(f"{adapter.name}: {e}")

    # Deduplicate across sources
    try:
        from regkb.intelligence.dedup import deduplicate_entries

        unique_entries = deduplicate_entries(all_entries)
    except ImportError:
        unique_entries = all_entries

    logger.info(
        "Fetched %d entries from %d sources (%d after dedup)",
        len(all_entries),
        sources_fetched,
        len(unique_entries),
    )

    return FetchResult(
        total_entries=len(unique_entries),
        entries=unique_entries,
        sources_fetched=sources_fetched,
        errors=all_errors,
        fetch_time=datetime.now(),
    )
