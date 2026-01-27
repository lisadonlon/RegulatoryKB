"""
Automatic version detection and diff generation for imported documents.

When a new document is imported, detects whether a prior version exists
in the KB and generates a comparison diff if so.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

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
    auto_superseded: bool = True


def _extract_title_terms(title: str) -> List[str]:
    """
    Extract key terms from a document title for content validation.

    Looks for regulatory identifiers, standard numbers, jurisdiction terms,
    and other substantive keywords that should appear in the document text.

    Returns:
        List of terms (lowercased) expected to appear in the document.
    """
    terms = []
    title_lower = title.lower()

    # Regulatory identifiers (MDR, IVDR, MDCG, CFR, etc.)
    id_patterns = [
        r'\b(mdr)\b',
        r'\b(ivdr)\b',
        r'\b(mdcg)\b',
        r'\b(cfr)\b',
        r'\b(iso)\b',
        r'\b(iec)\b',
        r'\b(imdrf)\b',
        r'\b(samd)\b',
    ]
    for pattern in id_patterns:
        if re.search(pattern, title_lower):
            terms.append(re.search(pattern, title_lower).group(1))

    # Document numbers like "2017/745", "13485", "62304", "14971"
    number_patterns = [
        r'(\d{4}/\d{3,4})',       # EU regulation numbers: 2017/745
        r'\b(\d{4,5})\b',         # Standard numbers: 13485, 62304
        r'(\d{4}-\d{1,4})',       # MDCG style: 2019-11, 2023-4
    ]
    for pattern in number_patterns:
        matches = re.findall(pattern, title)
        for m in matches:
            # Skip pure years (4-digit numbers between 1990-2030)
            if re.match(r'^\d{4}$', m) and 1990 <= int(m) <= 2030:
                continue
            terms.append(m.lower())

    # Jurisdiction terms
    jurisdiction_patterns = [
        r'\b(fda)\b',
        r'\b(eu|european)\b',
        r'\b(uk)\b',
    ]
    for pattern in jurisdiction_patterns:
        match = re.search(pattern, title_lower)
        if match:
            terms.append(match.group(1))

    return terms


def validate_content_matches_title(doc_id: int) -> Optional[str]:
    """
    Check whether the extracted text plausibly matches the document's title.

    Extracts key terms from the title (regulatory identifiers, standard
    numbers, jurisdictions) and checks if at least one appears in the
    first ~2000 characters of the extracted text.

    Args:
        doc_id: The document ID to validate.

    Returns:
        None if content looks valid, or a warning string if suspicious.
    """
    try:
        doc = db.get_document(doc_id=doc_id)
        if not doc:
            return None

        title = doc.get("title", "")
        terms = _extract_title_terms(title)

        if not terms:
            # No recognizable terms to check — can't validate
            return None

        # Read extracted text
        extracted_path = doc.get("extracted_path")
        if not extracted_path:
            return None  # No text to validate against

        extracted_file = Path(extracted_path)
        if not extracted_file.exists():
            return None

        # Read first ~2000 chars
        try:
            text = extracted_file.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:
            return None

        text_lower = text.lower()

        # Check if any expected term appears
        for term in terms:
            if term in text_lower:
                return None  # At least one term found — looks valid

        # No terms found — suspicious
        terms_str = ", ".join(f'"{t}"' for t in terms[:5])
        return (
            f"Content may not match title. "
            f"Expected terms ({terms_str}) not found in extracted text. "
            f"Verify this is the correct document."
        )

    except Exception as e:
        logger.debug(f"Content validation error for doc {doc_id}: {e}")
        return None


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
        auto_superseded = False

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

            # Similarity gate: only auto-supersede if above threshold
            min_similarity = config.get("versioning.min_supersession_similarity", 0.15)
            if stats and stats.similarity >= min_similarity:
                db.update_document(old_doc_id, is_latest=0, superseded_by=new_doc_id)
                auto_superseded = True
                logger.info(f"Marked doc [{old_doc_id}] as superseded by [{new_doc_id}]")
            else:
                similarity_pct = f"{stats.similarity:.1%}" if stats else "N/A"
                error = (
                    f"Similarity too low ({similarity_pct}) to auto-supersede. "
                    f"Minimum required: {min_similarity:.0%}. "
                    f"Use 'regkb diff {old_doc_id} {new_doc_id}' to review manually."
                )
                logger.warning(
                    f"Similarity gate blocked supersession of [{old_doc_id}] by [{new_doc_id}]: "
                    f"{similarity_pct} < {min_similarity:.0%}"
                )
        else:
            error = "Extracted text not available for diff"
            logger.warning(
                f"Could not generate diff between {old_doc_id} and {new_doc_id} "
                f"(extracted text may be missing)"
            )

        return VersionDiffResult(
            new_doc_id=new_doc_id,
            old_doc_id=old_doc_id,
            old_doc_title=old_title,
            new_doc_title=new_title,
            stats=stats or DiffStats(),
            diff_html_path=diff_html_path,
            error=error,
            auto_superseded=auto_superseded,
        )

    except Exception as e:
        logger.error(f"Version detection/diff failed for doc {new_doc_id}: {e}", exc_info=True)
        return None
