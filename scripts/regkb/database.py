"""
Database management for the Regulatory Knowledge Base.

Handles SQLite database operations including schema creation, CRUD operations,
and full-text search using FTS5.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from .config import config


class Database:
    """Database manager for the Regulatory Knowledge Base."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize the database manager.

        Args:
            db_path: Optional path to the database file. Uses config default if not provided.
        """
        self.db_path = db_path or config.database_path
        self._ensure_directory()
        self._init_schema()

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database connections.

        Yields:
            SQLite connection with row factory set to sqlite3.Row.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        with self.connection() as conn:
            cursor = conn.cursor()

            # Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    version TEXT,
                    is_latest BOOLEAN DEFAULT 1,
                    source_url TEXT,
                    file_path TEXT NOT NULL,
                    extracted_path TEXT,
                    description TEXT,
                    download_date TEXT NOT NULL,
                    import_date TEXT NOT NULL,
                    superseded_by INTEGER REFERENCES documents(id),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Full-text search virtual table
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    title,
                    description,
                    extracted_text,
                    content='documents',
                    content_rowid='id',
                    tokenize='porter unicode61'
                )
            """)

            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                    INSERT INTO documents_fts(rowid, title, description, extracted_text)
                    VALUES (new.id, new.title, new.description, '');
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, title, description, extracted_text)
                    VALUES ('delete', old.id, old.title, old.description, '');
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, title, description, extracted_text)
                    VALUES ('delete', old.id, old.title, old.description, '');
                    INSERT INTO documents_fts(rowid, title, description, extracted_text)
                    VALUES (new.id, new.title, new.description, '');
                END
            """)

            # Import batches table for audit trail
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    total_files INTEGER DEFAULT 0,
                    imported INTEGER DEFAULT 0,
                    duplicates INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'in_progress'
                )
            """)

            # Import batch items for detailed tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_batch_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER NOT NULL REFERENCES import_batches(id),
                    file_path TEXT NOT NULL,
                    document_id INTEGER REFERENCES documents(id),
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_jurisdiction ON documents(jurisdiction)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_is_latest ON documents(is_latest)")

    def document_exists(self, file_hash: str) -> bool:
        """
        Check if a document with the given hash exists.

        Args:
            file_hash: SHA-256 hash of the document.

        Returns:
            True if document exists, False otherwise.
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM documents WHERE hash = ?",
                (file_hash,)
            )
            return cursor.fetchone() is not None

    def add_document(
        self,
        file_hash: str,
        title: str,
        document_type: str,
        jurisdiction: str,
        file_path: str,
        version: Optional[str] = None,
        source_url: Optional[str] = None,
        description: Optional[str] = None,
        download_date: Optional[str] = None,
    ) -> int:
        """
        Add a new document to the database.

        Args:
            file_hash: SHA-256 hash of the document.
            title: Human-readable title.
            document_type: Type of document.
            jurisdiction: Jurisdiction (EU, FDA, etc.).
            file_path: Path to the archived PDF.
            version: Optional version identifier.
            source_url: Optional source URL.
            description: Optional description.
            download_date: Date the document was downloaded.

        Returns:
            The ID of the newly created document.
        """
        now = datetime.now().isoformat()
        download_date = download_date or now

        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents (
                    hash, title, document_type, jurisdiction, file_path,
                    version, source_url, description, download_date, import_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_hash, title, document_type, jurisdiction, file_path,
                    version, source_url, description, download_date, now
                )
            )
            return cursor.lastrowid

    def get_document(self, doc_id: Optional[int] = None, file_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID or hash.

        Args:
            doc_id: Document ID.
            file_hash: Document hash.

        Returns:
            Document data as dictionary or None if not found.
        """
        with self.connection() as conn:
            if doc_id:
                cursor = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            elif file_hash:
                cursor = conn.execute("SELECT * FROM documents WHERE hash = ?", (file_hash,))
            else:
                return None

            row = cursor.fetchone()
            return dict(row) if row else None

    def update_document(self, doc_id: int, **kwargs) -> bool:
        """
        Update a document's metadata.

        Args:
            doc_id: Document ID.
            **kwargs: Fields to update.

        Returns:
            True if document was updated, False otherwise.
        """
        if not kwargs:
            return False

        allowed_fields = {
            "title", "document_type", "jurisdiction", "version",
            "is_latest", "source_url", "description", "extracted_path",
            "superseded_by"
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        updates["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [doc_id]

        with self.connection() as conn:
            cursor = conn.execute(
                f"UPDATE documents SET {set_clause} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0

    def list_documents(
        self,
        document_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        latest_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List documents with optional filtering.

        Args:
            document_type: Filter by document type.
            jurisdiction: Filter by jurisdiction.
            latest_only: Only return latest versions.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of document dictionaries.
        """
        conditions = []
        params = []

        if document_type:
            conditions.append("document_type = ?")
            params.append(document_type)

        if jurisdiction:
            conditions.append("jurisdiction = ?")
            params.append(jurisdiction)

        if latest_only:
            conditions.append("is_latest = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        with self.connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT * FROM documents
                WHERE {where_clause}
                ORDER BY title
                LIMIT ? OFFSET ?
                """,
                params
            )
            return [dict(row) for row in cursor.fetchall()]

    def search_fts(
        self,
        query: str,
        limit: int = 10,
        latest_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search documents using full-text search.

        Args:
            query: Search query.
            limit: Maximum number of results.
            latest_only: Only return latest versions.

        Returns:
            List of matching documents with relevance scores.
        """
        latest_filter = "AND d.is_latest = 1" if latest_only else ""

        with self.connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT d.*, bm25(documents_fts) as relevance
                FROM documents_fts fts
                JOIN documents d ON fts.rowid = d.id
                WHERE documents_fts MATCH ?
                {latest_filter}
                ORDER BY relevance
                LIMIT ?
                """,
                (query, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary containing various statistics.
        """
        with self.connection() as conn:
            stats = {}

            # Total documents
            cursor = conn.execute("SELECT COUNT(*) FROM documents")
            stats["total_documents"] = cursor.fetchone()[0]

            # By document type
            cursor = conn.execute(
                "SELECT document_type, COUNT(*) as count FROM documents GROUP BY document_type"
            )
            stats["by_type"] = {row["document_type"]: row["count"] for row in cursor.fetchall()}

            # By jurisdiction
            cursor = conn.execute(
                "SELECT jurisdiction, COUNT(*) as count FROM documents GROUP BY jurisdiction"
            )
            stats["by_jurisdiction"] = {row["jurisdiction"]: row["count"] for row in cursor.fetchall()}

            # Latest vs all versions
            cursor = conn.execute("SELECT COUNT(*) FROM documents WHERE is_latest = 1")
            stats["latest_versions"] = cursor.fetchone()[0]

            # Import batches
            cursor = conn.execute("SELECT COUNT(*) FROM import_batches")
            stats["total_imports"] = cursor.fetchone()[0]

            return stats

    def create_import_batch(self, source_path: str) -> int:
        """
        Create a new import batch record.

        Args:
            source_path: Source directory being imported.

        Returns:
            Batch ID.
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO import_batches (source_path, started_at) VALUES (?, ?)",
                (source_path, datetime.now().isoformat())
            )
            return cursor.lastrowid

    def update_import_batch(
        self,
        batch_id: int,
        total_files: Optional[int] = None,
        imported: Optional[int] = None,
        duplicates: Optional[int] = None,
        errors: Optional[int] = None,
        status: Optional[str] = None,
    ) -> None:
        """Update an import batch record."""
        updates = {}
        if total_files is not None:
            updates["total_files"] = total_files
        if imported is not None:
            updates["imported"] = imported
        if duplicates is not None:
            updates["duplicates"] = duplicates
        if errors is not None:
            updates["errors"] = errors
        if status is not None:
            updates["status"] = status
            if status == "completed":
                updates["completed_at"] = datetime.now().isoformat()

        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [batch_id]

        with self.connection() as conn:
            conn.execute(f"UPDATE import_batches SET {set_clause} WHERE id = ?", values)

    def backup(self) -> Path:
        """
        Create a backup of the database.

        Returns:
            Path to the backup file.
        """
        backup_dir = config.backups_dir
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"regulatory_backup_{timestamp}.db"

        with self.connection() as conn:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()

        return backup_path


# Global database instance
db = Database()
