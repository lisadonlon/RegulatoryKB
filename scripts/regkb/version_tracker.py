"""
Version tracking for regulatory documents.
Checks if documents in the knowledge base are current or have newer versions available.
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from pathlib import Path


@dataclass
class VersionInfo:
    """Information about a document's version status."""
    doc_id: int
    title: str
    jurisdiction: str
    current_version: Optional[str]
    latest_version: Optional[str]
    current_date: Optional[str]
    latest_date: Optional[str]
    is_current: bool
    status: str  # 'current', 'outdated', 'superseded', 'unknown'
    notes: str = ""
    update_url: str = ""


# Known latest versions of key regulatory documents
# Updated: January 2026
KNOWN_VERSIONS = {
    # EU MDR/IVDR
    "MDR 2017/745": {
        "latest_version": "Consolidated 2026-01-01",
        "latest_date": "2026-01-01",
        "check_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02017R0745-20260101",
        "notes": "Check EUR-Lex for latest consolidated version"
    },
    "IVDR 2017/746": {
        "latest_version": "Consolidated 2025-01-10",
        "latest_date": "2025-01-10",
        "check_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02017R0746-20250110",
        "notes": "Check EUR-Lex for latest consolidated version"
    },

    # MDCG Guidance - key documents with known versions
    "MDCG 2019-11": {
        "latest_version": "Rev. 1",
        "latest_date": "2025-06",
        "check_url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations/guidance-mdcg-endorsed-documents-and-other-guidance_en",
        "notes": "Software qualification and classification - updated June 2025"
    },
    "MDCG 2020-1": {
        "latest_version": "Rev. 1",
        "latest_date": "2020-09",
        "check_url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations/guidance-mdcg-endorsed-documents-and-other-guidance_en",
    },
    "MDCG 2020-5": {
        "latest_version": "Original",
        "latest_date": "2020-09",
        "check_url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations/guidance-mdcg-endorsed-documents-and-other-guidance_en",
    },
    "MDCG 2020-6": {
        "latest_version": "Original",
        "latest_date": "2020-09",
        "check_url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations/guidance-mdcg-endorsed-documents-and-other-guidance_en",
    },
    "MDCG 2019-16": {
        "latest_version": "Rev. 1",
        "latest_date": "2020-07",
        "check_url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations/guidance-mdcg-endorsed-documents-and-other-guidance_en",
        "notes": "Cybersecurity guidance"
    },
    "MDCG 2023-4": {
        "latest_version": "Original",
        "latest_date": "2023-10",
        "check_url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations/guidance-mdcg-endorsed-documents-and-other-guidance_en",
        "notes": "Software lifecycle processes"
    },
    "MDCG 2024-5": {
        "latest_version": "Original",
        "latest_date": "2024-06",
        "check_url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations/guidance-mdcg-endorsed-documents-and-other-guidance_en",
        "notes": "Clinical evaluation guidance"
    },

    # ISO Standards
    "ISO 13485": {
        "latest_version": "2016",
        "latest_date": "2016-03",
        "check_url": "https://www.iso.org/standard/59752.html",
        "notes": "QMS for medical devices - Amd 1:2024 draft under development"
    },
    "ISO 14971": {
        "latest_version": "2019",
        "latest_date": "2019-12",
        "check_url": "https://www.iso.org/standard/72704.html",
        "notes": "Risk management"
    },
    "IEC 62304": {
        "latest_version": "2006+A1:2015",
        "latest_date": "2015-06",
        "check_url": "https://www.iso.org/standard/64686.html",
        "notes": "Medical device software lifecycle - Edition 2 under development"
    },
    "ISO 14155": {
        "latest_version": "2020",
        "latest_date": "2020-07",
        "check_url": "https://www.iso.org/standard/71690.html",
        "notes": "Clinical investigations"
    },
    "ISO 10993-1": {
        "latest_version": "2018",
        "latest_date": "2018-08",
        "check_url": "https://www.iso.org/standard/68936.html",
        "notes": "Biological evaluation - Part 1"
    },
    "IEC 62366-1": {
        "latest_version": "2015+A1:2020",
        "latest_date": "2020-04",
        "check_url": "https://www.iso.org/standard/77436.html",
        "notes": "Usability engineering"
    },

    # US FDA
    "21 CFR Part 820": {
        "latest_version": "Current",
        "latest_date": "2024",
        "check_url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-820",
        "notes": "QSR - QMSR final rule published Feb 2024, effective Feb 2026"
    },

    # IMDRF
    "IMDRF SaMD N12": {
        "latest_version": "2014",
        "latest_date": "2014-09",
        "check_url": "https://www.imdrf.org/documents/software-medical-device-samd-key-definitions",
        "notes": "SaMD Key Definitions"
    },

    # UK
    "UK MDR 2002": {
        "latest_version": "2024 Amendment",
        "latest_date": "2024",
        "check_url": "https://www.legislation.gov.uk/uksi/2002/618",
        "notes": "Check legislation.gov.uk for latest amendments"
    },
}


def extract_version_from_title(title: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract version number and year from document title."""
    version = None
    year = None

    # Match patterns like "rev 1", "Rev. 2", "revision 3"
    rev_match = re.search(r'rev(?:ision)?\.?\s*(\d+)', title, re.IGNORECASE)
    if rev_match:
        version = f"Rev. {rev_match.group(1)}"

    # Match year patterns like "2020", "2019-11"
    year_match = re.search(r'\b(20\d{2})\b', title)
    if year_match:
        year = year_match.group(1)

    # Match version patterns like "v1.0", "V2"
    ver_match = re.search(r'v(?:ersion)?\.?\s*(\d+(?:\.\d+)?)', title, re.IGNORECASE)
    if ver_match and not version:
        version = f"v{ver_match.group(1)}"

    # Match edition patterns
    ed_match = re.search(r'ed(?:ition)?\.?\s*(\d+)', title, re.IGNORECASE)
    if ed_match and not version:
        version = f"Ed. {ed_match.group(1)}"

    return version, year


def normalize_doc_identifier(title: str) -> Optional[str]:
    """Extract normalized document identifier for matching against known versions."""
    title_lower = title.lower()

    # MDCG documents
    mdcg_match = re.search(r'mdcg\s*(\d{4})[- ]?(\d+)', title_lower)
    if mdcg_match:
        return f"MDCG {mdcg_match.group(1)}-{mdcg_match.group(2)}"

    # ISO/IEC standards
    iso_match = re.search(r'(iso|iec)\s*(\d{4,5})(?:[- :](\d+))?', title_lower)
    if iso_match:
        standard = iso_match.group(1).upper()
        number = iso_match.group(2)
        part = iso_match.group(3)
        if part:
            return f"{standard} {number}-{part}"
        return f"{standard} {number}"

    # MDR/IVDR
    if 'mdr' in title_lower and '2017' in title_lower:
        return "MDR 2017/745"
    if 'ivdr' in title_lower and '2017' in title_lower:
        return "IVDR 2017/746"

    # 21 CFR
    cfr_match = re.search(r'21\s*cfr\s*(?:part\s*)?(\d+)', title_lower)
    if cfr_match:
        return f"21 CFR Part {cfr_match.group(1)}"

    # UK MDR
    if 'uk' in title_lower and 'mdr' in title_lower and '2002' in title_lower:
        return "UK MDR 2002"

    # IMDRF SaMD
    if 'imdrf' in title_lower and 'samd' in title_lower:
        if 'definition' in title_lower:
            return "IMDRF SaMD N12"

    return None


def check_document_version(doc: dict) -> VersionInfo:
    """Check if a document is current against known versions."""
    title = doc.get('title', '')
    doc_id = doc.get('id', 0)
    jurisdiction = doc.get('jurisdiction', '')
    stored_version = doc.get('version')

    # Extract version info from title
    extracted_version, extracted_year = extract_version_from_title(title)
    current_version = stored_version or extracted_version or extracted_year

    # Try to match against known versions
    identifier = normalize_doc_identifier(title)

    if identifier and identifier in KNOWN_VERSIONS:
        known = KNOWN_VERSIONS[identifier]
        latest_version = known.get('latest_version')
        latest_date = known.get('latest_date')
        notes = known.get('notes', '')
        update_url = known.get('check_url', '')

        # Determine if current
        is_current = True
        status = 'current'

        # Simple version comparison
        if latest_version and current_version:
            # Check if versions match (basic comparison)
            if latest_version.lower() == current_version.lower():
                # Exact match - document is current
                is_current = True
                status = 'current'
            else:
                # Check if it's an older revision
                if 'rev' in latest_version.lower():
                    latest_rev = re.search(r'rev\.?\s*(\d+)', latest_version, re.IGNORECASE)
                    current_rev = re.search(r'rev\.?\s*(\d+)', current_version, re.IGNORECASE)
                    if latest_rev and current_rev:
                        if int(latest_rev.group(1)) > int(current_rev.group(1)):
                            is_current = False
                            status = 'outdated'

                # Check year in version string (not document identifier)
                # Only if versions don't match and no revision comparison was done
                if status == 'current' and extracted_year and latest_date:
                    latest_year = latest_date[:4]
                    # Only compare if the extracted year is from the version, not the doc ID
                    # Check if year appears in current_version string
                    if current_version and extracted_year in current_version:
                        if int(extracted_year) < int(latest_year):
                            is_current = False
                            status = 'outdated'
                    elif not current_version:
                        # No version string, use extracted year
                        if int(extracted_year) < int(latest_year):
                            is_current = False
                            status = 'outdated'

        return VersionInfo(
            doc_id=doc_id,
            title=title,
            jurisdiction=jurisdiction,
            current_version=current_version,
            latest_version=latest_version,
            current_date=extracted_year,
            latest_date=latest_date,
            is_current=is_current,
            status=status,
            notes=notes,
            update_url=update_url
        )

    # Unknown document - can't verify
    return VersionInfo(
        doc_id=doc_id,
        title=title,
        jurisdiction=jurisdiction,
        current_version=current_version,
        latest_version=None,
        current_date=extracted_year,
        latest_date=None,
        is_current=True,  # Assume current if unknown
        status='unknown',
        notes="Version not tracked - manual verification needed"
    )


def check_all_versions(db_path: str) -> List[VersionInfo]:
    """Check versions of all documents in the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, jurisdiction, version, document_type, import_date
        FROM documents
        ORDER BY jurisdiction, title
    """)

    results = []
    for row in cursor.fetchall():
        doc = dict(row)
        version_info = check_document_version(doc)
        results.append(version_info)

    conn.close()
    return results


def get_version_summary(results: List[VersionInfo]) -> dict:
    """Generate summary statistics from version check results."""
    summary = {
        'total': len(results),
        'current': sum(1 for r in results if r.status == 'current'),
        'outdated': sum(1 for r in results if r.status == 'outdated'),
        'superseded': sum(1 for r in results if r.status == 'superseded'),
        'unknown': sum(1 for r in results if r.status == 'unknown'),
        'by_jurisdiction': {}
    }

    for result in results:
        jur = result.jurisdiction or 'Other'
        if jur not in summary['by_jurisdiction']:
            summary['by_jurisdiction'][jur] = {
                'total': 0, 'current': 0, 'outdated': 0, 'unknown': 0
            }
        summary['by_jurisdiction'][jur]['total'] += 1
        summary['by_jurisdiction'][jur][result.status] += 1

    return summary


def print_version_report(results: List[VersionInfo], show_current: bool = False):
    """Print formatted version check report."""
    summary = get_version_summary(results)

    print("=" * 70)
    print("REGULATORY KNOWLEDGE BASE - VERSION CHECK REPORT")
    print("=" * 70)
    print()
    print(f"Total Documents:     {summary['total']}")
    print(f"Current:            {summary['current']}")
    print(f"Outdated:           {summary['outdated']}")
    print(f"Unknown/Untracked:  {summary['unknown']}")
    print()

    # Show outdated documents
    outdated = [r for r in results if r.status == 'outdated']
    if outdated:
        print("-" * 70)
        print("OUTDATED DOCUMENTS - Updates Available")
        print("-" * 70)
        for r in outdated:
            print(f"\n  [{r.jurisdiction}] {r.title}")
            print(f"    Current: {r.current_version or 'Unknown'}")
            print(f"    Latest:  {r.latest_version}")
            if r.notes:
                print(f"    Note:    {r.notes}")
            if r.update_url:
                print(f"    Check:   {r.update_url}")
    else:
        print("No outdated documents found!")

    # Show unknown (untracked)
    unknown = [r for r in results if r.status == 'unknown']
    if unknown:
        print()
        print("-" * 70)
        print(f"UNTRACKED DOCUMENTS ({len(unknown)}) - Manual verification needed")
        print("-" * 70)
        # Group by jurisdiction
        by_jur = {}
        for r in unknown:
            jur = r.jurisdiction or 'Other'
            if jur not in by_jur:
                by_jur[jur] = []
            by_jur[jur].append(r)

        for jur in sorted(by_jur.keys()):
            print(f"\n  {jur}:")
            for r in by_jur[jur][:5]:  # Show first 5 per jurisdiction
                print(f"    - {r.title[:60]}")
            if len(by_jur[jur]) > 5:
                print(f"    ... and {len(by_jur[jur]) - 5} more")

    # Optionally show current
    if show_current:
        current = [r for r in results if r.status == 'current']
        if current:
            print()
            print("-" * 70)
            print("CURRENT DOCUMENTS")
            print("-" * 70)
            for r in current:
                print(f"  [{r.jurisdiction}] {r.title}")
                print(f"    Version: {r.current_version or 'N/A'} (Latest: {r.latest_version})")


def export_version_report_csv(results: List[VersionInfo], output_path: str):
    """Export version check results to CSV."""
    import csv

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'ID', 'Title', 'Jurisdiction', 'Current Version',
            'Latest Version', 'Status', 'Notes', 'Check URL'
        ])

        for r in results:
            writer.writerow([
                r.doc_id,
                r.title,
                r.jurisdiction,
                r.current_version or '',
                r.latest_version or '',
                r.status,
                r.notes,
                r.update_url
            ])
