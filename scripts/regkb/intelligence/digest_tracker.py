"""
Digest tracking for email reply-based document downloads.

Tracks digest entries and their IDs to enable lookup when processing
email replies requesting document downloads.
"""

import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import config
from .filter import FilteredEntry

logger = logging.getLogger(__name__)

# Database path
DB_PATH = config.base_dir / "db" / "intelligence_digests.db"


@dataclass
class DigestEntry:
    """A tracked entry in a digest email."""

    entry_id: str  # e.g., "2026-0125-07"
    entry_hash: str  # Hash of title+link for deduplication
    title: str
    link: Optional[str]
    agency: str
    category: str
    date: str
    download_status: str = "pending"  # pending, downloaded, failed, manual_needed
    kb_doc_id: Optional[int] = None
    resolved_url: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class Digest:
    """A sent digest email with its entries."""

    digest_date: str  # YYYY-MM-DD
    sent_at: datetime
    entry_count: int
    message_id: Optional[str] = None


class DigestTracker:
    """Tracks digest entries for email reply processing."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize the digest tracker."""
        self.db_path = db_path or DB_PATH
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS digests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    digest_date TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    entry_count INTEGER NOT NULL,
                    message_id TEXT,
                    UNIQUE(digest_date)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS digest_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id TEXT NOT NULL UNIQUE,
                    entry_hash TEXT NOT NULL,
                    digest_date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    link TEXT,
                    agency TEXT,
                    category TEXT,
                    entry_date TEXT,
                    download_status TEXT DEFAULT 'pending',
                    kb_doc_id INTEGER,
                    resolved_url TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entry_id ON digest_entries(entry_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_digest_date ON digest_entries(digest_date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entry_hash ON digest_entries(entry_hash)
            """)

            # Table for tracking daily alert entries (deduplication)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sent_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_hash TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    agency TEXT,
                    sent_at TEXT NOT NULL,
                    alert_type TEXT DEFAULT 'daily'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sent_alerts_hash ON sent_alerts(entry_hash)
            """)

            conn.commit()

    def _generate_entry_hash(self, title: str, link: Optional[str]) -> str:
        """Generate a hash for deduplication."""
        content = f"{title.lower().strip()}|{(link or '').lower().strip()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def generate_entry_id(self, digest_date: datetime, sequence_number: int) -> str:
        """
        Generate entry ID in format YYYY-MMDD-NN.

        Args:
            digest_date: Date of the digest.
            sequence_number: Entry number within the digest (1-based).

        Returns:
            Entry ID string like "2026-0125-07".
        """
        return f"{digest_date.strftime('%Y-%m%d')}-{sequence_number:02d}"

    def parse_entry_id(self, entry_id: str) -> tuple[Optional[datetime], Optional[int]]:
        """
        Parse an entry ID into its components.

        Args:
            entry_id: Entry ID string (e.g., "2026-0125-07" or just "07").

        Returns:
            Tuple of (digest_date, sequence_number) or (None, sequence_number) for short IDs.
        """
        entry_id = entry_id.strip()

        # Handle full ID format: YYYY-MMDD-NN
        if len(entry_id) >= 10 and "-" in entry_id:
            parts = entry_id.split("-")
            if len(parts) == 3:
                try:
                    year = int(parts[0])
                    month_day = parts[1]
                    month = int(month_day[:2])
                    day = int(month_day[2:])
                    seq = int(parts[2])
                    return datetime(year, month, day), seq
                except (ValueError, IndexError):
                    pass

        # Handle short ID format: just the number
        try:
            seq = int(entry_id.lstrip("0") or "0")
            return None, seq
        except ValueError:
            return None, None

    def record_digest(
        self,
        entries: list[FilteredEntry],
        digest_date: Optional[datetime] = None,
        message_id: Optional[str] = None,
    ) -> list[DigestEntry]:
        """
        Record a sent digest and its entries.

        Args:
            entries: List of FilteredEntry objects included in the digest.
            digest_date: Date of the digest (defaults to now).
            message_id: Email Message-ID for threading.

        Returns:
            List of DigestEntry objects with assigned IDs.
        """
        digest_date = digest_date or datetime.now()
        date_str = digest_date.strftime("%Y-%m-%d")
        now = datetime.now().isoformat()

        tracked_entries = []

        with sqlite3.connect(self.db_path) as conn:
            # Record the digest
            conn.execute(
                """
                INSERT OR REPLACE INTO digests (digest_date, sent_at, entry_count, message_id)
                VALUES (?, ?, ?, ?)
                """,
                (date_str, now, len(entries), message_id),
            )

            # Record each entry
            for i, filtered_entry in enumerate(entries, start=1):
                entry = filtered_entry.entry
                entry_id = self.generate_entry_id(digest_date, i)
                entry_hash = self._generate_entry_hash(entry.title, entry.link)

                # Check if this entry already exists (by hash)
                cursor = conn.execute(
                    "SELECT entry_id FROM digest_entries WHERE entry_hash = ?",
                    (entry_hash,),
                )
                existing = cursor.fetchone()

                if existing:
                    # Entry already tracked, update with new digest
                    conn.execute(
                        """
                        UPDATE digest_entries
                        SET entry_id = ?, digest_date = ?, updated_at = ?
                        WHERE entry_hash = ?
                        """,
                        (entry_id, date_str, now, entry_hash),
                    )
                else:
                    # New entry
                    conn.execute(
                        """
                        INSERT INTO digest_entries (
                            entry_id, entry_hash, digest_date, title, link,
                            agency, category, entry_date, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry_id,
                            entry_hash,
                            date_str,
                            entry.title,
                            entry.link,
                            entry.agency,
                            entry.category,
                            entry.date,
                            now,
                        ),
                    )

                tracked_entry = DigestEntry(
                    entry_id=entry_id,
                    entry_hash=entry_hash,
                    title=entry.title,
                    link=entry.link,
                    agency=entry.agency or "",
                    category=entry.category or "",
                    date=entry.date or "",
                )
                tracked_entries.append(tracked_entry)

            conn.commit()

        logger.info(f"Recorded digest with {len(tracked_entries)} entries for {date_str}")
        return tracked_entries

    def lookup_entries(
        self,
        entry_ids: list[str],
        digest_date: Optional[datetime] = None,
    ) -> list[DigestEntry]:
        """
        Look up entries by their IDs.

        Args:
            entry_ids: List of entry IDs (full or short format).
            digest_date: Date to use for short IDs (defaults to most recent digest).

        Returns:
            List of found DigestEntry objects.
        """
        results = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # If no digest_date provided, get the most recent one
            if digest_date is None:
                cursor = conn.execute(
                    "SELECT digest_date FROM digests ORDER BY sent_at DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    digest_date = datetime.strptime(row["digest_date"], "%Y-%m-%d")

            for entry_id in entry_ids:
                parsed_date, seq = self.parse_entry_id(entry_id)

                if parsed_date:
                    # Full ID - search by exact ID
                    full_id = entry_id
                elif seq is not None and digest_date:
                    # Short ID - construct full ID from digest date
                    full_id = self.generate_entry_id(digest_date, seq)
                else:
                    logger.warning(f"Could not parse entry ID: {entry_id}")
                    continue

                cursor = conn.execute(
                    """
                    SELECT entry_id, entry_hash, title, link, agency, category,
                           entry_date, download_status, kb_doc_id, resolved_url, error_message
                    FROM digest_entries WHERE entry_id = ?
                    """,
                    (full_id,),
                )
                row = cursor.fetchone()

                if row:
                    results.append(
                        DigestEntry(
                            entry_id=row["entry_id"],
                            entry_hash=row["entry_hash"],
                            title=row["title"],
                            link=row["link"],
                            agency=row["agency"] or "",
                            category=row["category"] or "",
                            date=row["entry_date"] or "",
                            download_status=row["download_status"],
                            kb_doc_id=row["kb_doc_id"],
                            resolved_url=row["resolved_url"],
                            error_message=row["error_message"],
                        )
                    )
                else:
                    logger.warning(f"Entry not found: {full_id}")

        return results

    def update_entry_status(
        self,
        entry_id: str,
        status: str,
        kb_doc_id: Optional[int] = None,
        resolved_url: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update the download status of an entry.

        Args:
            entry_id: Entry ID to update.
            status: New status (pending, downloaded, failed, manual_needed).
            kb_doc_id: KB document ID if downloaded.
            resolved_url: Resolved document URL.
            error_message: Error message if failed.

        Returns:
            True if entry was found and updated.
        """
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE digest_entries
                SET download_status = ?,
                    kb_doc_id = COALESCE(?, kb_doc_id),
                    resolved_url = COALESCE(?, resolved_url),
                    error_message = ?,
                    updated_at = ?
                WHERE entry_id = ?
                """,
                (status, kb_doc_id, resolved_url, error_message, now, entry_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_recent_entries(
        self,
        digest_date: Optional[str] = None,
        limit: int = 50,
    ) -> list[DigestEntry]:
        """
        Get recent digest entries.

        Args:
            digest_date: Filter by digest date (YYYY-MM-DD).
            limit: Maximum entries to return.

        Returns:
            List of DigestEntry objects.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if digest_date:
                cursor = conn.execute(
                    """
                    SELECT entry_id, entry_hash, title, link, agency, category,
                           entry_date, download_status, kb_doc_id, resolved_url, error_message
                    FROM digest_entries
                    WHERE digest_date = ?
                    ORDER BY entry_id
                    LIMIT ?
                    """,
                    (digest_date, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT entry_id, entry_hash, title, link, agency, category,
                           entry_date, download_status, kb_doc_id, resolved_url, error_message
                    FROM digest_entries
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            return [
                DigestEntry(
                    entry_id=row["entry_id"],
                    entry_hash=row["entry_hash"],
                    title=row["title"],
                    link=row["link"],
                    agency=row["agency"] or "",
                    category=row["category"] or "",
                    date=row["entry_date"] or "",
                    download_status=row["download_status"],
                    kb_doc_id=row["kb_doc_id"],
                    resolved_url=row["resolved_url"],
                    error_message=row["error_message"],
                )
                for row in cursor.fetchall()
            ]

    def get_stats(self) -> dict:
        """Get digest tracking statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) FROM digests")
            stats["total_digests"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM digest_entries")
            stats["total_entries"] = cursor.fetchone()[0]

            cursor = conn.execute(
                """
                SELECT download_status, COUNT(*) as count
                FROM digest_entries
                GROUP BY download_status
                """
            )
            stats["by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute("SELECT digest_date FROM digests ORDER BY sent_at DESC LIMIT 1")
            row = cursor.fetchone()
            stats["last_digest_date"] = row[0] if row else None

            # Add sent alerts count
            cursor = conn.execute("SELECT COUNT(*) FROM sent_alerts")
            stats["total_sent_alerts"] = cursor.fetchone()[0]

            return stats

    def was_alert_sent(self, title: str, link: Optional[str]) -> bool:
        """
        Check if an entry was already sent as a daily alert.

        Args:
            title: Entry title.
            link: Entry link (optional).

        Returns:
            True if this entry was already sent as an alert.
        """
        entry_hash = self._generate_entry_hash(title, link)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM sent_alerts WHERE entry_hash = ?",
                (entry_hash,),
            )
            return cursor.fetchone() is not None

    def record_sent_alerts(
        self,
        entries: list[FilteredEntry],
        alert_type: str = "daily",
    ) -> int:
        """
        Record entries that were sent as alerts.

        Args:
            entries: List of FilteredEntry objects that were sent.
            alert_type: Type of alert (daily, critical, etc.).

        Returns:
            Number of entries recorded (excludes duplicates).
        """
        now = datetime.now().isoformat()
        recorded = 0

        with sqlite3.connect(self.db_path) as conn:
            for filtered_entry in entries:
                entry = filtered_entry.entry
                entry_hash = self._generate_entry_hash(entry.title, entry.link)

                try:
                    conn.execute(
                        """
                        INSERT INTO sent_alerts (entry_hash, title, agency, sent_at, alert_type)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (entry_hash, entry.title, entry.agency, now, alert_type),
                    )
                    recorded += 1
                except sqlite3.IntegrityError:
                    # Already exists (duplicate hash)
                    pass

            conn.commit()

        logger.info(f"Recorded {recorded} sent alerts (type: {alert_type})")
        return recorded

    def filter_unsent_alerts(self, entries: list[FilteredEntry]) -> list[FilteredEntry]:
        """
        Filter out entries that have already been sent as alerts.

        Args:
            entries: List of FilteredEntry objects to filter.

        Returns:
            List of entries that have NOT been sent yet.
        """
        unsent = []

        for entry in entries:
            if not self.was_alert_sent(entry.entry.title, entry.entry.link):
                unsent.append(entry)

        if len(entries) > len(unsent):
            logger.info(
                f"Filtered out {len(entries) - len(unsent)} already-sent alerts "
                f"({len(unsent)} remaining)"
            )

        return unsent


# Global tracker instance
digest_tracker = DigestTracker()
