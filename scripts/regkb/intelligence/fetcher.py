"""
Newsletter fetcher for Index-of-Indexes regulatory updates.

Fetches regulatory updates from the Index-of-Indexes CSV sources.
"""

import csv
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Base URL for Index-of-Indexes
BASE_URL = "https://martincking.github.io/Index-of-Indexes"

# CSV source files
CSV_SOURCES_URL = f"{BASE_URL}/csv_sources.txt"
URL_CSV_URL = f"{BASE_URL}/URL.csv"
AGENCIES_CSV_URL = f"{BASE_URL}/Agencies.csv"

# Request settings
REQUEST_TIMEOUT = 30
USER_AGENT = "RegulatoryKB/1.0 (Regulatory Intelligence Agent)"


@dataclass
class NewsletterEntry:
    """Represents a single entry from the regulatory newsletter."""

    date: str
    agency: str
    category: str
    title: str
    link: Optional[str] = None
    date_parsed: Optional[datetime] = None

    def __post_init__(self):
        """Parse the date string into a datetime object."""
        if self.date and not self.date_parsed:
            try:
                # Try common date formats
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y", "%d. %B %Y"):
                    try:
                        self.date_parsed = datetime.strptime(self.date.strip(), fmt)
                        break
                    except ValueError:
                        continue
            except Exception:
                logger.debug(f"Could not parse date: {self.date}")


@dataclass
class FetchResult:
    """Results from a newsletter fetch operation."""

    total_entries: int = 0
    entries: List[NewsletterEntry] = field(default_factory=list)
    sources_fetched: int = 0
    errors: List[str] = field(default_factory=list)
    fetch_time: Optional[datetime] = None

    def __str__(self) -> str:
        return (
            f"Fetched {self.total_entries} entries from {self.sources_fetched} sources"
            f"{f' ({len(self.errors)} errors)' if self.errors else ''}"
        )


class NewsletterFetcher:
    """Fetches and parses regulatory updates from Index-of-Indexes."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """
        Initialize the newsletter fetcher.

        Args:
            cache_dir: Optional directory for caching fetched data.
        """
        self.cache_dir = cache_dir
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        # URL and agency mappings
        self._url_map: Dict[str, str] = {}
        self._agency_map: Dict[str, str] = {}

    def _fetch_url(self, url: str) -> Tuple[bool, str]:
        """
        Fetch content from a URL.

        Args:
            url: URL to fetch.

        Returns:
            Tuple of (success, content_or_error).
        """
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return True, response.text
        except requests.exceptions.Timeout:
            return False, f"Timeout fetching {url}"
        except requests.exceptions.HTTPError as e:
            return False, f"HTTP error {e.response.status_code} for {url}"
        except requests.exceptions.RequestException as e:
            return False, f"Request failed for {url}: {str(e)}"

    def _load_csv_sources(self) -> List[str]:
        """
        Load the list of CSV source URLs.

        Returns:
            List of CSV source URLs.
        """
        success, content = self._fetch_url(CSV_SOURCES_URL)
        if not success:
            logger.error(f"Failed to load CSV sources: {content}")
            return []

        sources = []
        for line in content.strip().split("\n"):
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith("#"):
                # Handle relative URLs
                if not line.startswith("http"):
                    line = f"{BASE_URL}/{line}"
                sources.append(line)

        logger.info(f"Found {len(sources)} CSV sources")
        return sources

    def _load_url_mappings(self) -> None:
        """Load date-to-URL mappings."""
        success, content = self._fetch_url(URL_CSV_URL)
        if not success:
            logger.warning(f"Could not load URL mappings: {content}")
            return

        reader = csv.reader(StringIO(content))
        for row in reader:
            if len(row) >= 2:
                date_key = row[0].strip()
                url = row[1].strip()
                if date_key and url:
                    self._url_map[date_key] = url

        logger.debug(f"Loaded {len(self._url_map)} URL mappings")

    def _load_agency_mappings(self) -> None:
        """Load agency-to-URL mappings."""
        success, content = self._fetch_url(AGENCIES_CSV_URL)
        if not success:
            logger.warning(f"Could not load agency mappings: {content}")
            return

        reader = csv.reader(StringIO(content))
        for row in reader:
            if len(row) >= 2:
                agency = row[0].strip()
                url = row[1].strip()
                if agency and url:
                    self._agency_map[agency.lower()] = url

        logger.debug(f"Loaded {len(self._agency_map)} agency mappings")

    def _parse_csv_data(self, csv_content: str, source_url: str) -> List[NewsletterEntry]:
        """
        Parse CSV content into newsletter entries.

        Args:
            csv_content: Raw CSV content.
            source_url: URL the content was fetched from (for logging).

        Returns:
            List of parsed entries.
        """
        entries = []
        try:
            reader = csv.reader(StringIO(csv_content))
            headers = None

            for row in reader:
                if not row or all(not cell.strip() for cell in row):
                    continue

                # First non-empty row might be headers
                if headers is None:
                    # Check if this looks like a header row
                    first_cell = row[0].strip().lower()
                    if first_cell in ("date", "datum", "fecha"):
                        headers = [h.strip().lower() for h in row]
                        continue
                    else:
                        # Assume standard column order: Date, Agency, Category, Title, [Link]
                        headers = ["date", "agency", "category", "title", "link"]

                # Parse data row
                if len(row) >= 4:
                    entry = NewsletterEntry(
                        date=row[0].strip() if len(row) > 0 else "",
                        agency=row[1].strip() if len(row) > 1 else "",
                        category=row[2].strip() if len(row) > 2 else "",
                        title=row[3].strip() if len(row) > 3 else "",
                        link=row[4].strip() if len(row) > 4 and row[4].strip() else None,
                    )
                    if entry.title:  # Only add if there's a title
                        entries.append(entry)

        except csv.Error as e:
            logger.warning(f"CSV parsing error for {source_url}: {e}")

        return entries

    def fetch(
        self,
        days: int = 7,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> FetchResult:
        """
        Fetch newsletter entries.

        Args:
            days: Number of days to look back (default 7 for weekly).
            start_date: Optional start date for custom range.
            end_date: Optional end date for custom range.

        Returns:
            FetchResult with all fetched entries.
        """
        result = FetchResult(fetch_time=datetime.now())

        # Calculate date range
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=days)

        logger.info(f"Fetching entries from {start_date.date()} to {end_date.date()}")

        # Load mappings
        self._load_url_mappings()
        self._load_agency_mappings()

        # Get CSV sources
        sources = self._load_csv_sources()
        if not sources:
            result.errors.append("No CSV sources available")
            return result

        # Fetch all sources
        all_entries = []
        for source_url in sources:
            success, content = self._fetch_url(source_url)
            if success:
                entries = self._parse_csv_data(content, source_url)
                all_entries.extend(entries)
                result.sources_fetched += 1
                logger.debug(f"Parsed {len(entries)} entries from {source_url}")
            else:
                result.errors.append(content)
                logger.warning(content)

        # Filter by date range
        filtered_entries = []
        unparsed_count = 0
        for entry in all_entries:
            if entry.date_parsed:
                if start_date <= entry.date_parsed <= end_date:
                    filtered_entries.append(entry)
            else:
                # Exclude entries we couldn't parse dates for
                unparsed_count += 1
                logger.debug(f"Excluding entry with unparseable date: {entry.date} - {entry.title[:50]}")

        if unparsed_count > 0:
            logger.warning(f"Excluded {unparsed_count} entries with unparseable dates")

        # Deduplicate by title (case-insensitive)
        seen_titles = set()
        unique_entries = []
        for entry in filtered_entries:
            title_key = entry.title.lower().strip()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_entries.append(entry)

        result.entries = unique_entries
        result.total_entries = len(unique_entries)

        logger.info(f"Fetched {result.total_entries} unique entries in date range")
        return result

    def fetch_this_week(self) -> FetchResult:
        """
        Convenience method to fetch this week's entries.

        Returns:
            FetchResult with this week's entries.
        """
        return self.fetch(days=7)

    def fetch_this_month(self) -> FetchResult:
        """
        Convenience method to fetch this month's entries.

        Returns:
            FetchResult with this month's entries.
        """
        return self.fetch(days=30)


# Global fetcher instance
fetcher = NewsletterFetcher()
