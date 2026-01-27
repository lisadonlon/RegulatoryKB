"""
Automatic version detection and diff generation for imported documents.

When a new document is imported, detects whether a prior version exists
in the KB and generates a comparison diff if so.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import config
from .database import db
from .diff import DiffStats, compare_documents
from .version_tracker import normalize_doc_identifier

logger = logging.getLogger(__name__)


@dataclass
class VersionDiffResult:
    """Result of automatic version detection and diff generation."""

    new_doc_id: int
    old_doc_id: int
    old_doc_title: str
    new_doc_title: str
    stats: DiffStats
    diff_html_path: Optional[str] = None
    error: Optional[str] = None


def find_prior_version(doc_id: int) -> Optional[dict]:
    """
    Find the most recent prior version of a document in the KB.

    Uses normalize_doc_identifier() to extract a standard identifier from the
    new document's title, then searches for other documents with the same
    identifier that are currently marked is_latest=1.

    Args:
        doc_id: The ID of the newly imported document.

    Returns:
        The prior document dict, or None if no match found.
    """
    new_doc = db.get_document(doc_id=doc_id)
    if not new_doc:
        return None

    new_title = new_doc.get("title", "")
    identifier = normalize_doc_identifier(new_title)
    if not identifier:
        logger.debug(f"No standard identifier found for doc {doc_id}: '{new_title}'")
        return None

    # Query all latest documents except the new one
    with db.connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM documents WHERE id != ? AND is_latest = 1 ORDER BY import_date DESC",
            (doc_id,),
        )
        candidates = [dict(row) for row in cursor.fetchall()]

    for candidate in candidates:
        candidate_title = candidate.get("title", "")
        candidate_identifier = normalize_doc_identifier(candidate_title)
        if candidate_identifier and candidate_identifier == identifier:
            logger.info(
                f"Found prior version: [{candidate['id']}] '{candidate_title}' "
                f"matches identifier '{identifier}'"
            )
            return candidate

    logger.debug(f"No prior version found for identifier '{identifier}'")
    return None


def detect_and_diff(new_doc_id: int) -> Optional[VersionDiffResult]:
    """
    Detect if a prior version exists and generate a diff.

    This is the main entry point called after any successful import.
    If a prior version is found:
      1. Generates an HTML diff and saves it to reports/diffs/
      2. Marks the old document as not latest (is_latest=0)
      3. Sets superseded_by on the old document to point to new_doc_id

    Args:
        new_doc_id: The ID of the newly imported document.

    Returns:
        VersionDiffResult if a prior version was found and diffed,
        None if no prior version exists.
    """
    try:
        prior_doc = find_prior_version(new_doc_id)
        if not prior_doc:
            return None

        old_doc_id = prior_doc["id"]
        old_title = prior_doc.get("title", f"Document {old_doc_id}")

        new_doc = db.get_document(doc_id=new_doc_id)
        new_title = new_doc.get("title", f"Document {new_doc_id}")

        # Generate the diff with HTML
        diff_result = compare_documents(
            doc1_id=old_doc_id,
            doc2_id=new_doc_id,
            doc1_title=f"{old_title} (prior)",
            doc2_title=f"{new_title} (new)",
            context_lines=3,
            include_html=True,
        )

        diff_html_path = None
        stats = None
        error = None

        if diff_result:
            stats = diff_result.stats

            # Save HTML diff to persistent location
            if diff_result.html_diff:
                diff_dir = config.diffs_dir
                diff_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                identifier = normalize_doc_identifier(new_title) or "unknown"
                safe_id = identifier.replace(" ", "_").replace("/", "-")
                filename = f"diff_{safe_id}_{old_doc_id}_vs_{new_doc_id}_{timestamp}.html"
                diff_path = diff_dir / filename
                diff_path.write_text(diff_result.html_diff, encoding="utf-8")
                diff_html_path = str(diff_path)
                logger.info(f"Diff HTML saved to: {diff_html_path}")
        else:
            error = "Extracted text not available for diff"
            logger.warning(
                f"Could not generate diff between {old_doc_id} and {new_doc_id} "
                f"(extracted text may be missing)"
            )

        # Mark old document as superseded
        db.update_document(old_doc_id, is_latest=0, superseded_by=new_doc_id)
        logger.info(f"Marked doc [{old_doc_id}] as superseded by [{new_doc_id}]")

        return VersionDiffResult(
            new_doc_id=new_doc_id,
            old_doc_id=old_doc_id,
            old_doc_title=old_title,
            new_doc_title=new_title,
            stats=stats or DiffStats(),
            diff_html_path=diff_html_path,
            error=error,
        )

    except Exception as e:
        logger.error(f"Version detection/diff failed for doc {new_doc_id}: {e}", exc_info=True)
        return None
