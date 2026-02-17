"""
Content filtering and relevance scoring for regulatory intelligence.

Filters newsletter entries based on configured interests and keywords.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .fetcher import NewsletterEntry

logger = logging.getLogger(__name__)


# Default filter configuration
DEFAULT_FILTER_CONFIG: dict[str, Any] = {
    "include_categories": [
        "Medical Devices",
        "Standards",
        "Digital Health",
        "AI/ML",
        "Software",
        "IVD",
        "Guidance",
    ],
    "exclude_categories": [
        "Pharmaceuticals",
        "Biologics",
        "Drug",
        "Vaccines",
    ],
    "include_keywords": [
        "MDR",
        "IVDR",
        "FDA",
        "guidance",
        "SaMD",
        "medical device",
        "IVD",
        "ISO 13485",
        "ISO 14971",
        "IEC 62304",
        "digital health",
        "AI",
        "machine learning",
        "cybersecurity",
        "software",
        "CE mark",
        "MDCG",
        "notified body",
        "UDI",
        "EUDAMED",
        "510(k)",
        "PMA",
        "De Novo",
    ],
    "exclude_keywords": [
        "drug",
        "pharmaceutical",
        "clinical trial",
        "biologics",
        "vaccine",
        "gene therapy",
        "biosimilar",
    ],
    "combination_device_keywords": [
        "drug-device",
        "combination product",
        "drug eluting",
        "prefilled",
        "delivery device",
        "combination device",
    ],
    "daily_alert_keywords": {
        "critical": [
            "MDR",
            "IVDR",
            "FDA final guidance",
            "ISO 13485",
            "recall",
            "safety alert",
            "warning letter",
        ],
        "high": [
            "SaMD",
            "AI/ML",
            "digital health",
            "cybersecurity",
            "MDCG",
            "draft guidance",
        ],
    },
    # News freshness filter - exclude old documents unless truly new
    "news_freshness": {
        "enabled": True,
        # Exclude documents with years older than this many years ago
        "max_document_age_years": 1,
        # Keywords that indicate genuine news (override old year filter)
        "new_content_keywords": [
            "new",
            "draft",
            "proposed",
            "released",
            "published",
            "announces",
            "updated",
            "revision",
            "rev.",
            "amendment",
            "effective",
            "final",
            "enters into force",
        ],
        # Keywords that indicate discussion of old content (not news)
        "discussion_keywords": [
            "webinar",
            "training",
            "overview",
            "introduction to",
            "understanding",
            "guide to",
            "summary of",
            "recap",
            "explained",
        ],
    },
}


@dataclass
class FilteredEntry:
    """A newsletter entry with filtering and relevance information."""

    entry: NewsletterEntry
    relevance_score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)
    matched_categories: list[str] = field(default_factory=list)
    is_combination_device: bool = False
    alert_level: Optional[str] = None  # "critical", "high", or None

    @property
    def should_alert(self) -> bool:
        """Whether this entry should trigger a daily alert."""
        return self.alert_level in ("critical", "high")


@dataclass
class FilterResult:
    """Results from a filtering operation."""

    total_input: int = 0
    included: list[FilteredEntry] = field(default_factory=list)
    excluded: list[NewsletterEntry] = field(default_factory=list)
    high_priority: list[FilteredEntry] = field(default_factory=list)

    @property
    def total_included(self) -> int:
        return len(self.included)

    @property
    def total_excluded(self) -> int:
        return len(self.excluded)

    def __str__(self) -> str:
        return (
            f"Filtered: {self.total_included} included, "
            f"{self.total_excluded} excluded, "
            f"{len(self.high_priority)} high priority"
        )

    def by_category(self) -> dict[str, list[FilteredEntry]]:
        """Group included entries by category."""
        grouped: dict[str, list[FilteredEntry]] = {}
        for entry in self.included:
            category = entry.entry.category or "Other"
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(entry)
        return grouped

    def by_agency(self) -> dict[str, list[FilteredEntry]]:
        """Group included entries by agency."""
        grouped: dict[str, list[FilteredEntry]] = {}
        for entry in self.included:
            agency = entry.entry.agency or "Other"
            if agency not in grouped:
                grouped[agency] = []
            grouped[agency].append(entry)
        return grouped


class ContentFilter:
    """Filters and scores newsletter entries based on configured interests."""

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        """
        Initialize the content filter.

        Args:
            config: Filter configuration. Uses defaults if not provided.
        """
        self.config = config or _load_filter_config()

        # Compile keyword patterns for efficient matching
        self._include_patterns: list[re.Pattern] = []
        self._exclude_patterns: list[re.Pattern] = []
        self._combination_patterns: list[re.Pattern] = []
        self._alert_patterns: dict[str, list[re.Pattern]] = {"critical": [], "high": []}

        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile keyword patterns for efficient matching."""
        # Include keywords
        for kw in self.config.get("include_keywords", []):
            pattern = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
            self._include_patterns.append(pattern)

        # Exclude keywords
        for kw in self.config.get("exclude_keywords", []):
            pattern = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
            self._exclude_patterns.append(pattern)

        # Combination device keywords
        for kw in self.config.get("combination_device_keywords", []):
            pattern = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
            self._combination_patterns.append(pattern)

        # Alert keywords
        alert_config = self.config.get("daily_alert_keywords", {})
        for level in ("critical", "high"):
            for kw in alert_config.get(level, []):
                pattern = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
                self._alert_patterns[level].append(pattern)

    def _get_searchable_text(self, entry: NewsletterEntry) -> str:
        """Get the combined text to search for an entry."""
        parts = [
            entry.title or "",
            entry.category or "",
            entry.agency or "",
        ]
        return " ".join(parts)

    def _check_category_match(self, entry: NewsletterEntry) -> tuple[bool, bool, list[str]]:
        """
        Check if entry category matches include/exclude lists.

        Returns:
            Tuple of (is_included, is_excluded, matched_categories).
        """
        include_cats = self.config.get("include_categories", [])
        exclude_cats = self.config.get("exclude_categories", [])

        category = (entry.category or "").lower()
        matched = []

        # Check includes
        is_included = False
        for cat in include_cats:
            if cat.lower() in category or category in cat.lower():
                is_included = True
                matched.append(cat)

        # Check excludes
        is_excluded = False
        for cat in exclude_cats:
            if cat.lower() in category or category in cat.lower():
                is_excluded = True

        return is_included, is_excluded, matched

    def _check_combination_device(self, text: str) -> bool:
        """Check if text indicates a combination device."""
        for pattern in self._combination_patterns:
            if pattern.search(text):
                return True
        return False

    def _has_exclude_keywords(self, text: str) -> tuple[bool, int]:
        """
        Check if text contains exclude keywords.

        Returns:
            Tuple of (has_excludes, count).
        """
        count = 0
        for pattern in self._exclude_patterns:
            if pattern.search(text):
                count += 1
        return count > 0, count

    def _check_news_freshness(self, entry: NewsletterEntry) -> tuple[bool, Optional[str]]:
        """
        Check if entry is genuinely new news vs discussion of old documents.

        Returns:
            Tuple of (is_fresh_news, reason_if_excluded).
        """
        freshness_config = self.config.get("news_freshness", {})
        if not freshness_config.get("enabled", True):
            return True, None

        text = f"{entry.title or ''} {entry.category or ''}".lower()
        title = entry.title or ""

        max_age = freshness_config.get("max_document_age_years", 1)
        current_year = datetime.now().year
        cutoff_year = current_year - max_age

        # Find year references in the title (e.g., "2020", "2019-11", ":2016")
        year_pattern = r"(?:^|[:\s\-/])(\d{4})(?:[:\s\-/]|$)"
        year_matches = re.findall(year_pattern, title)

        # Also check for patterns like "MDCG 2020-16" or "ISO 13485:2016"
        doc_year_pattern = r"(?:MDCG|ISO|IEC|FDA|EU)\s*(\d{4})"
        doc_year_matches = re.findall(doc_year_pattern, title, re.IGNORECASE)

        all_years = [
            int(y) for y in year_matches + doc_year_matches if 2000 <= int(y) <= current_year
        ]

        if not all_years:
            # No year found, assume it's current news
            return True, None

        oldest_year = min(all_years)

        if oldest_year >= cutoff_year:
            # Document is recent enough
            return True, None

        # Document has an old year reference - check if it's genuinely new content
        new_keywords = freshness_config.get("new_content_keywords", [])
        for kw in new_keywords:
            if kw.lower() in text:
                # Contains a "new" keyword - this might be a revision or update
                return True, None

        # Check if it's just a discussion/webinar about old content
        discussion_keywords = freshness_config.get("discussion_keywords", [])
        for kw in discussion_keywords:
            if kw.lower() in text:
                return False, f"Discussion of {oldest_year} document"

        # Old document without clear indication of being new
        return False, f"Document from {oldest_year} (older than {cutoff_year})"

    def _calculate_relevance(self, entry: NewsletterEntry) -> tuple[float, list[str]]:
        """
        Calculate relevance score based on keyword matches.

        Returns:
            Tuple of (score 0.0-1.0, list of matched keywords).
        """
        text = self._get_searchable_text(entry)
        matched_keywords = []

        # Count include keyword matches
        include_count = 0
        for i, pattern in enumerate(self._include_patterns):
            if pattern.search(text):
                include_count += 1
                kw = self.config.get("include_keywords", [])[i]
                matched_keywords.append(kw)

        # Count exclude keyword matches (negative weight)
        exclude_count = 0
        for pattern in self._exclude_patterns:
            if pattern.search(text):
                exclude_count += 1

        # Calculate score
        total_include = len(self._include_patterns) or 1
        include_score = include_count / total_include

        # Apply exclusion penalty (but don't go below 0)
        if exclude_count > 0:
            exclude_penalty = exclude_count * 0.2
            include_score = max(0, include_score - exclude_penalty)

        return include_score, matched_keywords

    def _check_alert_level(self, text: str) -> Optional[str]:
        """
        Check if entry should trigger a daily alert.

        Returns:
            Alert level ("critical", "high") or None.
        """
        # Check critical first
        for pattern in self._alert_patterns["critical"]:
            if pattern.search(text):
                return "critical"

        # Check high priority (need 2+ matches)
        high_matches = sum(1 for p in self._alert_patterns["high"] if p.search(text))
        if high_matches >= 2:
            return "high"

        return None

    def filter(self, entries: list[NewsletterEntry]) -> FilterResult:
        """
        Filter a list of newsletter entries.

        Args:
            entries: List of entries to filter.

        Returns:
            FilterResult with included and excluded entries.
        """
        result = FilterResult(total_input=len(entries))
        old_doc_count = 0

        for entry in entries:
            text = self._get_searchable_text(entry)

            # Check news freshness first (filter out old documents)
            is_fresh, freshness_reason = self._check_news_freshness(entry)
            if not is_fresh:
                old_doc_count += 1
                result.excluded.append(entry)
                continue

            # Check for combination device (overrides pharma/ICH exclusion)
            is_combination = self._check_combination_device(text)

            # Check for exclude keywords in title and category only (not agency name)
            exclude_text = f"{entry.title} {entry.category or ''}"
            has_excludes, exclude_count = self._has_exclude_keywords(exclude_text)

            # Check category match
            cat_included, cat_excluded, matched_cats = self._check_category_match(entry)

            # Calculate keyword relevance
            relevance, matched_kws = self._calculate_relevance(entry)

            # Determine if entry should be included
            should_include = False

            # Device-specific indicators — used to confirm device relevance
            device_indicators = [
                "medical device",
                "IVD",
                "in vitro diagnostic",
                "SaMD",
                "510(k)",
                "PMA",
                "De Novo",
                "MDR",
                "IVDR",
                "MDD",
                "CE mark",
                "MDCG",
                "notified body",
                "UDI",
                "EUDAMED",
                "MDSAP",
                "CDRH",
                "IEC 62304",
                "ISO 13485",
                "ISO 14971",
                "cybersecurity",
            ]
            has_device_keyword = any(kw.lower() in text.lower() for kw in device_indicators)

            # Minimum relevance threshold from config
            min_relevance = self.config.get("min_relevance_score", 0.0)

            # If multiple exclude keywords found, exclude (unless combination device)
            if exclude_count >= 2 and not is_combination:
                should_include = False
            elif cat_included and not cat_excluded and not has_excludes:
                # Category matches and no exclude keywords
                # Still require device relevance — "Guidance" category is too broad
                should_include = has_device_keyword or relevance > min_relevance
            elif cat_included and not cat_excluded and has_excludes:
                # Category matches but has exclude keywords — require strong device indicator
                should_include = has_device_keyword
            elif cat_excluded and is_combination:
                # Override exclusion for combination devices
                should_include = True
            elif cat_excluded or has_excludes:
                # Category is explicitly excluded or has exclude keywords - do not include
                should_include = False
            elif relevance > 0.1:
                # Include based on keyword relevance only if no exclusions
                should_include = has_device_keyword

            if should_include:
                # Check alert level
                alert_level = self._check_alert_level(text)

                filtered_entry = FilteredEntry(
                    entry=entry,
                    relevance_score=relevance,
                    matched_keywords=matched_kws,
                    matched_categories=matched_cats,
                    is_combination_device=is_combination,
                    alert_level=alert_level,
                )
                result.included.append(filtered_entry)

                if alert_level:
                    result.high_priority.append(filtered_entry)
            else:
                result.excluded.append(entry)

        # Sort included by relevance score (descending)
        result.included.sort(key=lambda x: x.relevance_score, reverse=True)
        result.high_priority.sort(
            key=lambda x: (0 if x.alert_level == "critical" else 1, -x.relevance_score)
        )

        if old_doc_count > 0:
            logger.info(f"Filtered out {old_doc_count} old document references")
        logger.info(str(result))
        return result

    def update_config(self, new_config: dict[str, Any]) -> None:
        """
        Update filter configuration.

        Args:
            new_config: New configuration to merge with existing.
        """
        self.config.update(new_config)
        self._compile_patterns()


# Load filter config from config.yaml if available
def _load_filter_config() -> dict[str, Any]:
    """Load filter configuration from config.yaml."""
    try:
        from ..config import config as app_config

        filter_config = DEFAULT_FILTER_CONFIG.copy()

        # Load category filters
        if app_config.get("intelligence.filters.include_categories"):
            filter_config["include_categories"] = app_config.get(
                "intelligence.filters.include_categories"
            )
        if app_config.get("intelligence.filters.exclude_categories"):
            filter_config["exclude_categories"] = app_config.get(
                "intelligence.filters.exclude_categories"
            )

        # Load keyword filters
        if app_config.get("intelligence.filters.include_keywords"):
            filter_config["include_keywords"] = app_config.get(
                "intelligence.filters.include_keywords"
            )
        if app_config.get("intelligence.filters.exclude_keywords"):
            filter_config["exclude_keywords"] = app_config.get(
                "intelligence.filters.exclude_keywords"
            )
        if app_config.get("intelligence.filters.combination_device_keywords"):
            filter_config["combination_device_keywords"] = app_config.get(
                "intelligence.filters.combination_device_keywords"
            )

        # Load alert keywords
        if app_config.get("intelligence.alerts.critical_keywords"):
            filter_config["daily_alert_keywords"]["critical"] = app_config.get(
                "intelligence.alerts.critical_keywords"
            )
        if app_config.get("intelligence.alerts.high_keywords"):
            filter_config["daily_alert_keywords"]["high"] = app_config.get(
                "intelligence.alerts.high_keywords"
            )

        # Load news freshness config
        if app_config.get("intelligence.news_freshness"):
            filter_config["news_freshness"] = app_config.get("intelligence.news_freshness")

        return filter_config
    except Exception:
        return DEFAULT_FILTER_CONFIG


# Global filter instance
content_filter = ContentFilter(_load_filter_config())
