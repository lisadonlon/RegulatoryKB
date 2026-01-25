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
from .fetcher import (
    NewsletterEntry,
    FetchResult,
    NewsletterFetcher,
    fetcher,
)

# Filter - Content filtering and relevance scoring
from .filter import (
    FilteredEntry,
    FilterResult,
    ContentFilter,
    content_filter,
)

# Analyzer - KB integration and download queue
from .analyzer import (
    AnalysisResult,
    AnalysisSummary,
    PendingDownload,
    KBAnalyzer,
    analyzer,
)

# Summarizer - LLM-powered summaries
from .summarizer import (
    Summary,
    Summarizer,
    summarizer,
)

# Emailer - Email delivery
from .emailer import (
    Emailer,
    emailer,
)

# Scheduler - Automated execution support
from .scheduler import (
    SchedulerState,
    scheduler_state,
    generate_windows_task_xml,
    generate_batch_script,
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
