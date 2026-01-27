"""
Regulatory Intelligence Module

Automated monitoring and analysis of regulatory updates from Index-of-Indexes.

This module provides:
- Newsletter fetching from Index-of-Indexes CSV sources
- Content filtering based on configurable interests
- KB integration to identify new documents
- LLM-powered summarization via Claude
- Email delivery for weekly/daily/monthly digests
- Scheduled execution support
"""

__version__ = "1.0.0"

# Fetcher - Newsletter data retrieval
# Analyzer - KB integration and download queue
from .analyzer import (
    AnalysisResult,
    AnalysisSummary,
    KBAnalyzer,
    PendingDownload,
    analyzer,
)

# Emailer - Email delivery
from .emailer import (
    Emailer,
    emailer,
)
from .fetcher import (
    FetchResult,
    NewsletterEntry,
    NewsletterFetcher,
    fetcher,
)

# Filter - Content filtering and relevance scoring
from .filter import (
    ContentFilter,
    FilteredEntry,
    FilterResult,
    content_filter,
)

# Scheduler - Automated execution support
from .scheduler import (
    SchedulerState,
    generate_batch_script,
    generate_windows_task_xml,
    scheduler_state,
)

# Summarizer - LLM-powered summaries
from .summarizer import (
    Summarizer,
    Summary,
    summarizer,
)

__all__ = [
    # Version
    "__version__",
    # Fetcher
    "NewsletterEntry",
    "FetchResult",
    "NewsletterFetcher",
    "fetcher",
    # Filter
    "FilteredEntry",
    "FilterResult",
    "ContentFilter",
    "content_filter",
    # Analyzer
    "AnalysisResult",
    "AnalysisSummary",
    "PendingDownload",
    "KBAnalyzer",
    "analyzer",
    # Summarizer
    "Summary",
    "Summarizer",
    "summarizer",
    # Emailer
    "Emailer",
    "emailer",
    # Scheduler
    "SchedulerState",
    "scheduler_state",
    "generate_windows_task_xml",
    "generate_batch_script",
]
