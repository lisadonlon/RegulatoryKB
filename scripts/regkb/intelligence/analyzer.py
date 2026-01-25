"""
Knowledge base analyzer for regulatory intelligence.

Compares newsletter entries against existing KB documents to identify
new documents and manage the download approval queue.
"""

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config import config
from .filter import FilteredEntry

logger = logging.getLogger(__name__)

# Pending downloads database
PENDING_DB_NAME = "intelligence_pending.db"


@dataclass
class AnalysisResult:
    """Result of analyzing a filtered entry against the KB."""

    entry: FilteredEntry
    in_kb: bool = False
    kb_doc_id: Optional[int] = None
    kb_match_type: Optional[str] = None  # "url", "title", "hash"
    kb_match_score: float = 0.0
    is_downloadable: bool = False
    download_url: Optional[str] = None
    requires_manual: bool = False
    manual_reason: Optional[str] = None


@dataclass
class AnalysisSummary:
    """Summary of KB analysis results."""

    total_analyzed: int = 0
    already_in_kb: int = 0
    new_downloadable: int = 0
    requires_manual: int = 0
    results: List[AnalysisResult] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Analyzed {self.total_analyzed}: "
            f"{self.already_in_kb} in KB, "
            f"{self.new_downloadable} downloadable, "
            f"{self.requires_manual} manual"
        )


@dataclass
class PendingDownload:
    """A document pending approval for download."""

    id: int
    title: str
    url: str
    agency: str
    category: str
    date: str
    relevance_score: float
    keywords: List[str]
    status: str  # "pending", "approved", "rejected", "downloaded", "failed"
    created_at: str
    updated_at: str
    doc_id: Optional[int] = None  # Set after successful import


class KBAnalyzer:
    """Analyzes newsletter entries against the knowledge base."""

    # URL patterns for downloadable PDFs
    PDF_PATTERNS = [
        r"\.pdf$",
        r"\.pdf\?",
        r"/pdf/",
        r"download.*pdf",
    ]

    # Domains that typically host free regulatory PDFs
    FREE_PDF_DOMAINS = [
        "fda.gov",
        "europa.eu",
        "ec.europa.eu",
        "health.ec.europa.eu",
        "eur-lex.europa.eu",
        "who.int",
        "iso.org/obp",  # ISO preview pages
        "gov.uk",
        "hpra.ie",
        "tga.gov.au",
    ]

    # Domains that require purchase/subscription
    PAID_DOMAINS = [
        "iso.org/standard",
        "webstore.iec.ch",
        "standards.iteh.ai",
        "bsigroup.com",
        "din.de",
    ]

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize the KB analyzer.

        Args:
            db_path: Path to the main regulatory KB database.
        """
        self.db_path = db_path or config.database_path
        self.pending_db_path = config.base_dir / "db" / PENDING_DB_NAME
        self._init_pending_db()

    def _init_pending_db(self) -> None:
        """Initialize the pending downloads database."""
        self.pending_db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.pending_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                agency TEXT,
                category TEXT,
                entry_date TEXT,
                relevance_score REAL,
                keywords TEXT,
                status TEXT DEFAULT 'pending',
                doc_id INTEGER,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_downloads(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_url ON pending_downloads(url)")
        conn.commit()
        conn.close()

    def _get_kb_documents(self) -> List[Dict[str, Any]]:
        """Get all documents from the KB for comparison."""
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, title, source_url, hash FROM documents WHERE is_latest = 1"
        )
        docs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return docs

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL for comparison."""
        if not url:
            return ""
        # Remove trailing slashes, query params, fragments
        url = url.lower().strip()
        url = re.sub(r"[?#].*$", "", url)
        url = url.rstrip("/")
        # Remove www prefix
        url = re.sub(r"^https?://(www\.)?", "", url)
        return url

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for comparison."""
        if not title:
            return ""
        # Lowercase, remove punctuation, normalize whitespace
        title = title.lower().strip()
        title = re.sub(r"[^\w\s]", " ", title)
        title = re.sub(r"\s+", " ", title)
        return title

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles."""
        t1 = self._normalize_title(title1)
        t2 = self._normalize_title(title2)
        return SequenceMatcher(None, t1, t2).ratio()

    def _check_url_match(self, entry_url: str, kb_docs: List[Dict]) -> Tuple[bool, Optional[int], float]:
        """Check if entry URL matches any KB document."""
        if not entry_url:
            return False, None, 0.0

        normalized_entry = self._normalize_url(entry_url)

        for doc in kb_docs:
            if doc.get("source_url"):
                normalized_kb = self._normalize_url(doc["source_url"])
                if normalized_entry == normalized_kb:
                    return True, doc["id"], 1.0

        return False, None, 0.0

    def _check_title_match(
        self, entry_title: str, kb_docs: List[Dict], threshold: float = 0.85
    ) -> Tuple[bool, Optional[int], float]:
        """Check if entry title matches any KB document title."""
        if not entry_title:
            return False, None, 0.0

        best_match = None
        best_score = 0.0

        for doc in kb_docs:
            score = self._title_similarity(entry_title, doc["title"])
            if score > best_score:
                best_score = score
                best_match = doc["id"]

        if best_score >= threshold:
            return True, best_match, best_score

        return False, None, best_score

    def _is_pdf_url(self, url: str) -> bool:
        """Check if URL likely points to a PDF."""
        if not url:
            return False

        url_lower = url.lower()
        for pattern in self.PDF_PATTERNS:
            if re.search(pattern, url_lower):
                return True
        return False

    def _is_free_domain(self, url: str) -> bool:
        """Check if URL is from a domain that typically offers free downloads."""
        if not url:
            return False

        url_lower = url.lower()
        for domain in self.FREE_PDF_DOMAINS:
            if domain in url_lower:
                return True
        return False

    def _is_paid_domain(self, url: str) -> Tuple[bool, Optional[str]]:
        """Check if URL is from a domain that requires payment."""
        if not url:
            return False, None

        url_lower = url.lower()
        for domain in self.PAID_DOMAINS:
            if domain in url_lower:
                return True, f"Requires purchase from {domain}"
        return False, None

    def _analyze_downloadability(self, url: str) -> Tuple[bool, bool, Optional[str]]:
        """
        Analyze if a URL is downloadable.

        Returns:
            Tuple of (is_downloadable, requires_manual, reason)
        """
        if not url:
            return False, True, "No URL provided"

        # Check if it's a paid domain
        is_paid, paid_reason = self._is_paid_domain(url)
        if is_paid:
            return False, True, paid_reason

        # Check if it's a direct PDF
        if self._is_pdf_url(url):
            return True, False, None

        # Check if it's from a free regulatory domain (might need to navigate to PDF)
        if self._is_free_domain(url):
            return True, False, None

        # Social media and blog links - useful for tracking but need manual review
        social_domains = ["linkedin.com", "twitter.com", "x.com", "medium.com", "substack.com"]
        url_lower = url.lower()
        for domain in social_domains:
            if domain in url_lower:
                return False, False, f"Social/blog link ({domain})"

        # Otherwise, might be downloadable - mark as potential
        return True, True, "May require navigation to find document"

    def analyze(self, filtered_entries: List[FilteredEntry]) -> AnalysisSummary:
        """
        Analyze filtered entries against the knowledge base.

        Args:
            filtered_entries: List of filtered newsletter entries.

        Returns:
            AnalysisSummary with results.
        """
        summary = AnalysisSummary(total_analyzed=len(filtered_entries))
        kb_docs = self._get_kb_documents()

        logger.info(f"Analyzing {len(filtered_entries)} entries against {len(kb_docs)} KB documents")

        for fe in filtered_entries:
            entry = fe.entry
            result = AnalysisResult(entry=fe)

            # Check URL match first
            url_match, url_doc_id, url_score = self._check_url_match(entry.link, kb_docs)
            if url_match:
                result.in_kb = True
                result.kb_doc_id = url_doc_id
                result.kb_match_type = "url"
                result.kb_match_score = url_score
                summary.already_in_kb += 1
                summary.results.append(result)
                continue

            # Check title match
            title_match, title_doc_id, title_score = self._check_title_match(entry.title, kb_docs)
            if title_match:
                result.in_kb = True
                result.kb_doc_id = title_doc_id
                result.kb_match_type = "title"
                result.kb_match_score = title_score
                summary.already_in_kb += 1
                summary.results.append(result)
                continue

            # Not in KB - check downloadability
            is_downloadable, requires_manual, manual_reason = self._analyze_downloadability(entry.link)

            result.is_downloadable = is_downloadable
            result.download_url = entry.link
            result.requires_manual = requires_manual
            result.manual_reason = manual_reason

            if is_downloadable:
                summary.new_downloadable += 1
            if requires_manual:
                summary.requires_manual += 1

            summary.results.append(result)

        logger.info(str(summary))
        return summary

    def queue_for_approval(self, results: List[AnalysisResult]) -> int:
        """
        Add downloadable entries to the pending approval queue.

        Args:
            results: Analysis results to queue.

        Returns:
            Number of entries queued.
        """
        queued = 0
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.pending_db_path)

        for result in results:
            if not result.in_kb and result.is_downloadable and result.download_url:
                entry = result.entry.entry
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO pending_downloads
                        (title, url, agency, category, entry_date, relevance_score, keywords, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry.title,
                            result.download_url,
                            entry.agency,
                            entry.category,
                            entry.date,
                            result.entry.relevance_score,
                            json.dumps(result.entry.matched_keywords),
                            now,
                            now,
                        ),
                    )
                    if conn.total_changes > 0:
                        queued += 1
                except sqlite3.IntegrityError:
                    # URL already in queue
                    pass

        conn.commit()
        conn.close()

        logger.info(f"Queued {queued} documents for approval")
        return queued

    def get_pending(self, status: str = "pending") -> List[PendingDownload]:
        """
        Get pending downloads by status.

        Args:
            status: Status filter ("pending", "approved", "rejected", "downloaded").

        Returns:
            List of pending downloads.
        """
        conn = sqlite3.connect(self.pending_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM pending_downloads WHERE status = ? ORDER BY relevance_score DESC",
            (status,),
        )
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append(
                PendingDownload(
                    id=row["id"],
                    title=row["title"],
                    url=row["url"],
                    agency=row["agency"] or "",
                    category=row["category"] or "",
                    date=row["entry_date"] or "",
                    relevance_score=row["relevance_score"] or 0.0,
                    keywords=json.loads(row["keywords"]) if row["keywords"] else [],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    doc_id=row["doc_id"],
                )
            )

        return results

    def approve(self, ids: List[int]) -> int:
        """
        Approve pending downloads.

        Args:
            ids: List of pending download IDs to approve.

        Returns:
            Number of items approved.
        """
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.pending_db_path)

        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE pending_downloads SET status = 'approved', updated_at = ? WHERE id IN ({placeholders}) AND status = 'pending'",
            [now] + ids,
        )
        count = conn.total_changes
        conn.commit()
        conn.close()

        logger.info(f"Approved {count} downloads")
        return count

    def reject(self, ids: List[int]) -> int:
        """
        Reject pending downloads.

        Args:
            ids: List of pending download IDs to reject.

        Returns:
            Number of items rejected.
        """
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.pending_db_path)

        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE pending_downloads SET status = 'rejected', updated_at = ? WHERE id IN ({placeholders}) AND status = 'pending'",
            [now] + ids,
        )
        count = conn.total_changes
        conn.commit()
        conn.close()

        logger.info(f"Rejected {count} downloads")
        return count

    def approve_all(self) -> int:
        """Approve all pending downloads."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.pending_db_path)
        conn.execute(
            "UPDATE pending_downloads SET status = 'approved', updated_at = ? WHERE status = 'pending'",
            (now,),
        )
        count = conn.total_changes
        conn.commit()
        conn.close()
        return count

    def mark_downloaded(self, pending_id: int, doc_id: int) -> None:
        """Mark a pending download as successfully downloaded and imported."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.pending_db_path)
        conn.execute(
            "UPDATE pending_downloads SET status = 'downloaded', doc_id = ?, updated_at = ? WHERE id = ?",
            (doc_id, now, pending_id),
        )
        conn.commit()
        conn.close()

    def mark_failed(self, pending_id: int, error: str) -> None:
        """Mark a pending download as failed."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.pending_db_path)
        conn.execute(
            "UPDATE pending_downloads SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
            (error, now, pending_id),
        )
        conn.commit()
        conn.close()

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about pending downloads."""
        conn = sqlite3.connect(self.pending_db_path)
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM pending_downloads GROUP BY status"
        )
        stats = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return stats


# Global analyzer instance
analyzer = KBAnalyzer()
