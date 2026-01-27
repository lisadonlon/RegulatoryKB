"""
Document comparison for the Regulatory Knowledge Base.

Provides side-by-side and unified diff of extracted document text,
with summary statistics and HTML report generation.
"""

import difflib
import logging
from dataclasses import dataclass
from typing import Optional

from .config import config

logger = logging.getLogger(__name__)


@dataclass
class DiffStats:
    """Summary statistics for a document comparison."""

    added: int = 0
    removed: int = 0
    changed: int = 0
    unchanged: int = 0
    similarity: float = 0.0

    @property
    def total(self) -> int:
        return self.added + self.removed + self.changed + self.unchanged

    def summary(self) -> str:
        parts = [
            f"Similarity: {self.similarity:.1%}",
            f"Added: {self.added}",
            f"Removed: {self.removed}",
            f"Changed: {self.changed}",
            f"Unchanged: {self.unchanged}",
        ]
        return " | ".join(parts)


@dataclass
class DiffResult:
    """Full result of a document comparison."""

    doc1_id: int
    doc2_id: int
    doc1_title: str
    doc2_title: str
    stats: DiffStats
    unified_diff: str = ""
    html_diff: str = ""


def compare_documents(
    doc1_id: int,
    doc2_id: int,
    doc1_title: str = "",
    doc2_title: str = "",
    context_lines: int = 3,
    include_html: bool = False,
) -> Optional[DiffResult]:
    """
    Compare two extracted documents.

    Args:
        doc1_id: First document ID.
        doc2_id: Second document ID.
        doc1_title: Display title for first document.
        doc2_title: Display title for second document.
        context_lines: Number of context lines in unified diff.
        include_html: Whether to generate HTML side-by-side diff.

    Returns:
        DiffResult or None if either document's extracted text is missing.
    """
    extracted_dir = config.extracted_dir

    path1 = extracted_dir / f"{doc1_id}.md"
    path2 = extracted_dir / f"{doc2_id}.md"

    if not path1.exists():
        logger.error(f"Extracted text not found for document {doc1_id}: {path1}")
        return None
    if not path2.exists():
        logger.error(f"Extracted text not found for document {doc2_id}: {path2}")
        return None

    text1 = path1.read_text(encoding="utf-8")
    text2 = path2.read_text(encoding="utf-8")

    lines1 = text1.splitlines(keepends=True)
    lines2 = text2.splitlines(keepends=True)

    label1 = doc1_title or f"Document {doc1_id}"
    label2 = doc2_title or f"Document {doc2_id}"

    stats = compute_diff_stats(lines1, lines2)
    unified = generate_unified_diff(lines1, lines2, label1, label2, context_lines)

    html = ""
    if include_html:
        html = generate_html_diff(lines1, lines2, label1, label2, context_lines)

    return DiffResult(
        doc1_id=doc1_id,
        doc2_id=doc2_id,
        doc1_title=label1,
        doc2_title=label2,
        stats=stats,
        unified_diff=unified,
        html_diff=html,
    )


def compute_diff_stats(lines1: list[str], lines2: list[str]) -> DiffStats:
    """
    Compute diff statistics between two sets of lines.

    Uses SequenceMatcher to classify lines as added, removed, changed, or unchanged.

    Args:
        lines1: Lines from the first document.
        lines2: Lines from the second document.

    Returns:
        DiffStats with counts and similarity ratio.
    """
    matcher = difflib.SequenceMatcher(None, lines1, lines2)
    stats = DiffStats()

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            stats.unchanged += i2 - i1
        elif tag == "replace":
            stats.changed += max(i2 - i1, j2 - j1)
        elif tag == "insert":
            stats.added += j2 - j1
        elif tag == "delete":
            stats.removed += i2 - i1

    stats.similarity = matcher.ratio()
    return stats


def generate_unified_diff(
    lines1: list[str],
    lines2: list[str],
    label1: str,
    label2: str,
    context_lines: int = 3,
) -> str:
    """
    Generate a unified diff string.

    Args:
        lines1: Lines from the first document.
        lines2: Lines from the second document.
        label1: Label for the first document.
        label2: Label for the second document.
        context_lines: Number of surrounding context lines.

    Returns:
        Unified diff as a string.
    """
    diff = difflib.unified_diff(
        lines1,
        lines2,
        fromfile=label1,
        tofile=label2,
        n=context_lines,
    )
    return "".join(diff)


def generate_html_diff(
    lines1: list[str],
    lines2: list[str],
    label1: str,
    label2: str,
    context_lines: int = 3,
) -> str:
    """
    Generate a side-by-side HTML diff report.

    Args:
        lines1: Lines from the first document.
        lines2: Lines from the second document.
        label1: Label for the first document.
        label2: Label for the second document.
        context_lines: Number of surrounding context lines.

    Returns:
        Complete HTML page as a string.
    """
    # Strip trailing newlines for HtmlDiff (it adds its own)
    clean1 = [line.rstrip("\n") for line in lines1]
    clean2 = [line.rstrip("\n") for line in lines2]

    differ = difflib.HtmlDiff(wrapcolumn=80)
    table = differ.make_file(
        clean1,
        clean2,
        fromdesc=label1,
        todesc=label2,
        context=True,
        numlines=context_lines,
    )
    return table
