"""
Gap analysis tool to identify missing regulatory documents.
Compares knowledge base contents against reference checklist.
"""

import re
import sqlite3
from dataclasses import dataclass
from typing import Optional

from .reference_docs import REFERENCE_DOCUMENTS


@dataclass
class MatchResult:
    """Represents a match between a reference doc and a KB document."""

    ref_id: str
    ref_title: str
    ref_description: str
    jurisdiction: str
    category: str
    mandatory: bool
    matched: bool
    kb_doc_id: Optional[int] = None
    kb_doc_title: Optional[str] = None
    match_confidence: float = 0.0


def normalize_title(title: str) -> str:
    """Normalize a title for matching."""
    title = title.lower()
    # Remove common prefixes/suffixes
    title = re.sub(r"\s*\(.*?\)\s*", " ", title)  # Remove parentheticals
    title = re.sub(r"\s*-\s*copy.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+v\d+.*$", "", title, flags=re.IGNORECASE)  # Version numbers
    title = re.sub(r"\s+rev\s*\d+.*$", "", title, flags=re.IGNORECASE)  # Revisions
    title = re.sub(r"\s+ed\.\d+.*$", "", title, flags=re.IGNORECASE)  # Editions
    title = re.sub(r"\s+en\s*$", "", title)  # Language suffix
    title = re.sub(r"[^a-z0-9\s]", " ", title)  # Remove special chars
    title = re.sub(r"\s+", " ", title).strip()  # Normalize whitespace
    return title


def extract_doc_identifiers(title: str) -> list[str]:
    """Extract document identifiers from title (ISO numbers, MDCG refs, etc.)."""
    identifiers = []

    # ISO/IEC standards (e.g., ISO 13485, IEC 62304, ISO/IEC 22989)
    iso_matches = re.findall(r"(?:iso|iec|en)[\s/]*(\d{4,5})(?:[-:]?\d+)?", title.lower())
    identifiers.extend([f"iso{m}" for m in iso_matches])

    # MDCG guidance (e.g., MDCG 2019-11, MDCG 2020-1)
    mdcg_matches = re.findall(r"mdcg[\s]*(\d{4})[\s-]*(\d+)", title.lower())
    identifiers.extend([f"mdcg{y}-{n}" for y, n in mdcg_matches])

    # CFR references (e.g., 21 CFR 820)
    cfr_matches = re.findall(r"(?:21\s*)?cfr[\s]*(?:part\s*)?(\d+)", title.lower())
    identifiers.extend([f"cfr{m}" for m in cfr_matches])

    # MDR/IVDR/MDD
    if "mdr" in title.lower() and "2017" in title:
        identifiers.append("mdr2017/745")
    if "ivdr" in title.lower() and "2017" in title:
        identifiers.append("ivdr2017/746")
    if "mdd" in title.lower() and "93" in title:
        identifiers.append("mdd93/42")

    # CELEX references
    celex_match = re.search(r"celex.*?(\d{4})[r]?(\d{3,4})", title.lower())
    if celex_match:
        identifiers.append(f"celex{celex_match.group(1)}{celex_match.group(2)}")

    return identifiers


def calculate_match_score(ref_doc: dict, kb_title: str, kb_jurisdiction: str) -> float:
    """Calculate how well a KB document matches a reference document."""
    score = 0.0

    ref_title = ref_doc["title"].lower()
    ref_desc = ref_doc.get("description", "").lower()
    kb_title_lower = kb_title.lower()
    kb_title_norm = normalize_title(kb_title)

    # Extract identifiers from both
    ref_identifiers = extract_doc_identifiers(ref_title)
    kb_identifiers = extract_doc_identifiers(kb_title)

    # Strong match: identifier match
    for ref_id in ref_identifiers:
        if ref_id in kb_identifiers:
            score += 0.8
            break

    # Check for title keywords
    ref_keywords = set(normalize_title(ref_title).split())
    kb_keywords = set(kb_title_norm.split())

    if ref_keywords and kb_keywords:
        overlap = len(ref_keywords & kb_keywords)
        keyword_score = overlap / max(len(ref_keywords), 1)
        score += keyword_score * 0.3

    # Check for description keywords in KB title
    if ref_desc:
        desc_keywords = set(normalize_title(ref_desc).split())
        desc_overlap = len(desc_keywords & kb_keywords)
        if desc_overlap >= 2:
            score += 0.1

    # Jurisdiction match bonus
    ref_jur = ref_doc.get("jurisdiction", "").lower()
    if ref_jur and kb_jurisdiction:
        if ref_jur == kb_jurisdiction.lower():
            score += 0.1
        elif ref_jur == "iso" and "iso" in kb_title_lower:
            score += 0.1

    return min(score, 1.0)


def find_best_match(ref_doc: dict, kb_docs: list[dict]) -> tuple[Optional[dict], float]:
    """Find the best matching KB document for a reference document."""
    best_match = None
    best_score = 0.0

    for kb_doc in kb_docs:
        score = calculate_match_score(ref_doc, kb_doc["title"], kb_doc.get("jurisdiction", ""))
        if score > best_score:
            best_score = score
            best_match = kb_doc

    # Only return match if confidence is above threshold
    if best_score >= 0.5:
        return best_match, best_score
    return None, 0.0


def run_gap_analysis(db_path: str) -> dict[str, list[MatchResult]]:
    """Run gap analysis comparing KB against reference documents."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all KB documents
    cursor.execute("SELECT id, title, document_type, jurisdiction FROM documents")
    kb_docs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    results = {}

    for jurisdiction, categories in REFERENCE_DOCUMENTS.items():
        results[jurisdiction] = []

        for category, ref_docs in categories.items():
            for ref_doc in ref_docs:
                # Find best match in KB
                match, confidence = find_best_match(ref_doc, kb_docs)

                result = MatchResult(
                    ref_id=ref_doc["id"],
                    ref_title=ref_doc["title"],
                    ref_description=ref_doc.get("description", ""),
                    jurisdiction=jurisdiction,
                    category=category,
                    mandatory=ref_doc.get("mandatory", False),
                    matched=match is not None,
                    kb_doc_id=match["id"] if match else None,
                    kb_doc_title=match["title"] if match else None,
                    match_confidence=confidence,
                )
                results[jurisdiction].append(result)

    return results


def get_gap_summary(results: dict[str, list[MatchResult]]) -> dict:
    """Generate summary statistics from gap analysis results."""
    summary = {
        "total_reference": 0,
        "total_matched": 0,
        "total_missing": 0,
        "mandatory_missing": 0,
        "by_jurisdiction": {},
    }

    for jurisdiction, matches in results.items():
        jur_total = len(matches)
        jur_matched = sum(1 for m in matches if m.matched)
        jur_missing = jur_total - jur_matched
        jur_mandatory_missing = sum(1 for m in matches if not m.matched and m.mandatory)

        summary["total_reference"] += jur_total
        summary["total_matched"] += jur_matched
        summary["total_missing"] += jur_missing
        summary["mandatory_missing"] += jur_mandatory_missing

        summary["by_jurisdiction"][jurisdiction] = {
            "total": jur_total,
            "matched": jur_matched,
            "missing": jur_missing,
            "mandatory_missing": jur_mandatory_missing,
            "coverage": round(jur_matched / jur_total * 100, 1) if jur_total > 0 else 0,
        }

    summary["overall_coverage"] = (
        round(summary["total_matched"] / summary["total_reference"] * 100, 1)
        if summary["total_reference"] > 0
        else 0
    )

    return summary


def print_gap_report(results: dict[str, list[MatchResult]], show_matched: bool = False):
    """Print a formatted gap analysis report."""
    summary = get_gap_summary(results)

    print("=" * 70)
    print("REGULATORY KNOWLEDGE BASE - GAP ANALYSIS REPORT")
    print("=" * 70)
    print()
    print(f"Overall Coverage: {summary['overall_coverage']}%")
    print(f"Total Reference Documents: {summary['total_reference']}")
    print(f"Documents Matched: {summary['total_matched']}")
    print(f"Documents Missing: {summary['total_missing']}")
    print(f"MANDATORY Documents Missing: {summary['mandatory_missing']}")
    print()

    # Priority order for display
    priority_order = ["EU", "UK", "US", "Canada", "Australia", "ISO", "IMDRF", "MDSAP"]

    for jurisdiction in priority_order:
        if jurisdiction not in results:
            continue

        matches = results[jurisdiction]
        jur_stats = summary["by_jurisdiction"][jurisdiction]

        print("-" * 70)
        print(
            f"{jurisdiction} - Coverage: {jur_stats['coverage']}% "
            f"({jur_stats['matched']}/{jur_stats['total']})"
        )
        print("-" * 70)

        # Group by category
        categories = {}
        for m in matches:
            if m.category not in categories:
                categories[m.category] = []
            categories[m.category].append(m)

        for category, cat_matches in categories.items():
            missing = [m for m in cat_matches if not m.matched]
            matched = [m for m in cat_matches if m.matched]

            if missing or show_matched:
                print(f"\n  [{category}]")

            # Show missing (prioritize mandatory)
            for m in sorted(missing, key=lambda x: not x.mandatory):
                mandatory_flag = " [MANDATORY]" if m.mandatory else ""
                print(f"    MISSING: {m.ref_title}{mandatory_flag}")
                print(f"             {m.ref_description}")

            # Optionally show matched
            if show_matched:
                for m in matched:
                    print(f"    OK: {m.ref_title}")
                    print(f"        -> {m.kb_doc_title[:50]}... (conf: {m.match_confidence:.0%})")

        print()


def get_missing_docs(
    results: dict[str, list[MatchResult]], mandatory_only: bool = False
) -> list[MatchResult]:
    """Get list of missing documents."""
    missing = []
    for matches in results.values():
        for m in matches:
            if not m.matched:
                if not mandatory_only or m.mandatory:
                    missing.append(m)
    return missing


def export_gap_report_csv(results: dict[str, list[MatchResult]], output_path: str):
    """Export gap analysis to CSV."""
    import csv

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Jurisdiction",
                "Category",
                "Ref ID",
                "Title",
                "Description",
                "Mandatory",
                "Status",
                "KB Match",
                "Confidence",
            ]
        )

        for _jurisdiction, matches in results.items():
            for m in matches:
                writer.writerow(
                    [
                        m.jurisdiction,
                        m.category,
                        m.ref_id,
                        m.ref_title,
                        m.ref_description,
                        "Yes" if m.mandatory else "No",
                        "Found" if m.matched else "MISSING",
                        m.kb_doc_title or "",
                        f"{m.match_confidence:.0%}" if m.matched else "",
                    ]
                )
