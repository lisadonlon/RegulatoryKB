"""
Document comparison for the Regulatory Knowledge Base.

Provides side-by-side and unified diff of extracted document text,
with summary statistics and HTML report generation.
"""

import csv
import difflib
import io
import logging
from dataclasses import dataclass
from datetime import datetime
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


def export_diff_csv(result: DiffResult) -> str:
    """Export diff result to CSV format."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Document A ID",
            "Document A Title",
            "Document B ID",
            "Document B Title",
            "Similarity %",
            "Lines Added",
            "Lines Removed",
            "Lines Changed",
            "Lines Unchanged",
            "Comparison Date",
        ]
    )
    writer.writerow(
        [
            result.doc1_id,
            result.doc1_title,
            result.doc2_id,
            result.doc2_title,
            f"{result.stats.similarity:.1%}",
            result.stats.added,
            result.stats.removed,
            result.stats.changed,
            result.stats.unchanged,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        ]
    )
    return output.getvalue()


def export_diff_markdown(result: DiffResult) -> str:
    """Export diff result to Markdown format with actionable summary."""
    lines = [
        "# Document Comparison Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Documents Compared",
        "",
        "| | Document A | Document B |",
        "|---|---|---|",
        f"| **ID** | {result.doc1_id} | {result.doc2_id} |",
        f"| **Title** | {result.doc1_title} | {result.doc2_title} |",
        "",
        "## Summary Statistics",
        "",
        f"- **Similarity:** {result.stats.similarity:.1%}",
        f"- **Lines Added:** {result.stats.added}",
        f"- **Lines Removed:** {result.stats.removed}",
        f"- **Lines Changed:** {result.stats.changed}",
        f"- **Lines Unchanged:** {result.stats.unchanged}",
        "",
        "## Action Items",
        "",
    ]

    # Generate action items based on diff stats
    if result.stats.similarity == 1.0:
        lines.append("- Documents are identical. No action required.")
    else:
        if result.stats.added > 0:
            lines.append(f"- [ ] Review {result.stats.added} added line(s) in Document B")
        if result.stats.removed > 0:
            lines.append(f"- [ ] Verify {result.stats.removed} removed line(s) from Document A")
        if result.stats.changed > 0:
            lines.append(f"- [ ] Examine {result.stats.changed} changed line(s)")
        if result.stats.similarity < 0.5:
            lines.append("- [ ] **Major changes detected** — consider full document review")

    lines.extend(
        [
            "",
            "## Unified Diff",
            "",
            "```diff",
            result.unified_diff if result.unified_diff else "(no differences)",
            "```",
        ]
    )

    return "\n".join(lines)


def export_diff_html_report(result: DiffResult) -> str:
    """Export diff result to a self-contained HTML report with actionable summary."""
    similarity_pct = result.stats.similarity * 100
    if similarity_pct >= 90:
        similarity_color = "#2ecc40"  # green
    elif similarity_pct >= 70:
        similarity_color = "#ffdc00"  # yellow
    else:
        similarity_color = "#ff4136"  # red

    # Generate action items HTML
    action_items = []
    if result.stats.similarity == 1.0:
        action_items.append("<li>Documents are identical. No action required.</li>")
    else:
        if result.stats.added > 0:
            action_items.append(
                f"<li>Review <strong>{result.stats.added}</strong> added line(s)</li>"
            )
        if result.stats.removed > 0:
            action_items.append(
                f"<li>Verify <strong>{result.stats.removed}</strong> removed line(s)</li>"
            )
        if result.stats.changed > 0:
            action_items.append(
                f"<li>Examine <strong>{result.stats.changed}</strong> changed line(s)</li>"
            )
        if result.stats.similarity < 0.5:
            action_items.append(
                '<li style="color: #ff4136;"><strong>Major changes detected</strong> '
                "— consider full document review</li>"
            )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comparison: {result.doc1_title} vs {result.doc2_title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 2rem; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 0.5rem; }}
        h2 {{ color: #555; margin-top: 2rem; }}
        .meta {{ color: #888; font-size: 0.9rem; margin-bottom: 2rem; }}
        .stats-grid {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
        .stat-card {{ text-align: center; padding: 1rem 1.5rem; border: 1px solid #ddd; border-radius: 6px; min-width: 100px; }}
        .stat-card.similarity {{ border-color: {similarity_color}; }}
        .stat-card.added {{ border-color: #2ecc40; }}
        .stat-card.removed {{ border-color: #ff4136; }}
        .stat-card.changed {{ border-color: #ff851b; }}
        .stat-value {{ font-size: 1.8rem; font-weight: bold; display: block; }}
        .stat-label {{ font-size: 0.85rem; color: #666; }}
        .doc-table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        .doc-table th, .doc-table td {{ padding: 0.75rem; border: 1px solid #ddd; text-align: left; }}
        .doc-table th {{ background: #f9f9f9; }}
        .action-list {{ background: #fffbe6; border: 1px solid #ffe58f; border-radius: 6px; padding: 1rem 1rem 1rem 2rem; }}
        .action-list li {{ margin: 0.5rem 0; }}
        .diff-container {{ margin-top: 2rem; border: 1px solid #ddd; border-radius: 6px; overflow: hidden; }}
        .diff-container iframe {{ width: 100%; height: 600px; border: none; }}
        @media print {{ body {{ background: white; }} .container {{ box-shadow: none; }} }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Document Comparison Report</h1>
        <p class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

        <h2>Documents Compared</h2>
        <table class="doc-table">
            <tr><th></th><th>Document A</th><th>Document B</th></tr>
            <tr><td><strong>ID</strong></td><td>{result.doc1_id}</td><td>{result.doc2_id}</td></tr>
            <tr><td><strong>Title</strong></td><td>{result.doc1_title}</td><td>{result.doc2_title}</td></tr>
        </table>

        <h2>Summary Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card similarity">
                <span class="stat-value">{similarity_pct:.1f}%</span>
                <span class="stat-label">Similarity</span>
            </div>
            <div class="stat-card added">
                <span class="stat-value">{result.stats.added}</span>
                <span class="stat-label">Added</span>
            </div>
            <div class="stat-card removed">
                <span class="stat-value">{result.stats.removed}</span>
                <span class="stat-label">Removed</span>
            </div>
            <div class="stat-card changed">
                <span class="stat-value">{result.stats.changed}</span>
                <span class="stat-label">Changed</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{result.stats.unchanged}</span>
                <span class="stat-label">Unchanged</span>
            </div>
        </div>

        <h2>Action Items</h2>
        <ul class="action-list">
            {"".join(action_items)}
        </ul>

        <h2>Side-by-Side Comparison</h2>
        <div class="diff-container">
            <iframe srcdoc="{result.html_diff.replace('"', "&quot;")}" sandbox></iframe>
        </div>
    </div>
</body>
</html>"""

    return html
