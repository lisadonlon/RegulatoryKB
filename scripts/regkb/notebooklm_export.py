"""NotebookLM export for RegulatoryKB intelligence pipeline (Use Case 1).

Hybrid source strategy:
  1. Text digest summary (Claude-generated) — gives NotebookLM "what happened"
  2. Local KB documents (PDFs/markdown) — already-vetted primary sources
  3. Targeted research queries — lets NotebookLM find additional primary sources

Usage:
    python -m regkb.notebooklm_export export-digest [--days 7]
    python -m regkb.notebooklm_export create-notebook [--title "..."] [--days 90]
    python -m regkb.notebooklm_export generate <type> [--instruction "..."]

Requires: shared_lib (C:\\Projects\\shared_lib), notebooklm-py venv.
"""

import argparse
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

# Ensure shared_lib is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared_lib import notebooklm_utils as nlm

logger = logging.getLogger(__name__)

# --- Constants ---

REGKB_ROOT = Path(__file__).resolve().parents[2]
SUMMARIES_DB = REGKB_ROOT / "db" / "intelligence_summaries.db"
DIGESTS_DB = REGKB_ROOT / "db" / "intelligence_digests.db"
REGULATORY_DB = REGKB_ROOT / "db" / "regulatory.db"

# Default notebook title template
NOTEBOOK_TITLE_TEMPLATE = "DLSC Regulatory Update — {date_range}"

# Max sources per notebook (NotebookLM limit is 50; leave headroom for research)
MAX_KB_DOCUMENTS = 15
MAX_URL_SOURCES = 10


# --- Data Classes ---


@dataclass
class DigestExport:
    """Exported digest data ready for NotebookLM."""

    title: str
    date_range: str
    summary_text: str
    entry_count: int
    source_urls: list[str] = field(default_factory=list)
    kb_document_paths: list[str] = field(default_factory=list)
    research_queries: list[str] = field(default_factory=list)


# --- Database Access ---


def get_recent_summaries(days: int = 7) -> list[dict]:
    """Fetch recent summaries from the intelligence summaries cache."""
    if not SUMMARIES_DB.exists():
        logger.warning("Summaries DB not found at %s", SUMMARIES_DB)
        return []

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    conn = sqlite3.connect(str(SUMMARIES_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT entry_title, entry_agency, entry_date,
                   what_happened, why_it_matters, action_needed,
                   full_summary, created_at
            FROM summaries
            WHERE created_at >= ?
            ORDER BY created_at DESC
            """,
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        logger.warning("Failed to query summaries: %s", e)
        return []
    finally:
        conn.close()


def get_recent_digest_entries(days: int = 7) -> list[dict]:
    """Fetch recent digest entries with links and KB doc associations."""
    if not DIGESTS_DB.exists():
        logger.warning("Digests DB not found at %s", DIGESTS_DB)
        return []

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    conn = sqlite3.connect(str(DIGESTS_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT entry_id, title, link, agency, category, entry_date,
                   download_status, kb_doc_id
            FROM digest_entries
            WHERE created_at >= ?
            ORDER BY created_at DESC
            """,
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        logger.warning("Failed to query digest entries: %s", e)
        return []
    finally:
        conn.close()


def get_kb_documents_for_entries(kb_doc_ids: list[int]) -> list[dict]:
    """Fetch KB document paths for digest entries that were downloaded.

    Returns documents with their extracted markdown or PDF file paths.
    """
    if not REGULATORY_DB.exists() or not kb_doc_ids:
        return []

    conn = sqlite3.connect(str(REGULATORY_DB))
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in kb_doc_ids)
        rows = conn.execute(
            f"""
            SELECT id, title, jurisdiction, file_path, extracted_path
            FROM documents
            WHERE id IN ({placeholders})
            """,
            kb_doc_ids,
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        logger.warning("Failed to query KB documents: %s", e)
        return []
    finally:
        conn.close()


def get_recent_kb_documents(days: int = 90, limit: int = MAX_KB_DOCUMENTS) -> list[dict]:
    """Fetch recently imported KB documents as potential NotebookLM sources.

    Prefers extracted markdown (smaller, cleaner) over raw PDFs.
    """
    if not REGULATORY_DB.exists():
        return []

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    conn = sqlite3.connect(str(REGULATORY_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, title, jurisdiction, document_type, file_path, extracted_path
            FROM documents
            WHERE import_date >= ? AND is_latest = 1
            ORDER BY import_date DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        logger.warning("Failed to query recent KB documents: %s", e)
        return []
    finally:
        conn.close()


# --- Research Query Generation ---


def generate_research_queries(summaries: list[dict], max_queries: int = 3) -> list[str]:
    """Generate targeted research queries from high-priority summaries.

    Extracts key topics from digest summaries to let NotebookLM find
    the actual primary source documents (FDA guidance, MDCG docs, etc.).
    """
    queries = []

    # Group by agency and pick the most impactful entries
    by_agency: dict[str, list[dict]] = {}
    for s in summaries:
        agency = s.get("entry_agency", "Unknown")
        by_agency.setdefault(agency, []).append(s)

    # Build one research query per major agency grouping
    for agency, items in sorted(by_agency.items(), key=lambda x: -len(x[1])):
        if len(queries) >= max_queries:
            break

        # Use the first entry's title as the basis for a research query
        titles = [item.get("entry_title", "") for item in items[:3]]
        # Extract key terms: remove generic words, keep regulatory specifics
        combined = " ".join(titles)

        # Build a targeted query
        if "FDA" in agency or "CDRH" in agency:
            query = f"FDA medical device guidance {combined[:80]} 2025 2026"
        elif "EU" in agency or "MDCG" in agency or "European" in agency:
            query = f"EU MDR MDCG medical device {combined[:80]} 2025 2026"
        elif "MHRA" in agency or "UK" in agency or "GOV.UK" in agency:
            query = f"MHRA UK medical device {combined[:80]} 2025 2026"
        else:
            query = f"medical device regulatory {agency} {combined[:60]} 2025 2026"

        queries.append(query[:150])  # NotebookLM query length limit

    return queries


# --- Export Functions ---


def format_digest_for_notebooklm(
    summaries: list[dict],
    entries: list[dict],
    days: int = 7,
) -> DigestExport:
    """Format digest data into structured text with hybrid source strategy."""
    now = datetime.now()
    start = now - timedelta(days=days)
    date_range = f"{start.strftime('%d %b')} – {now.strftime('%d %b %Y')}"

    # --- Build text summary ---
    lines = []
    lines.append("# DLSC Regulatory Intelligence Digest")
    lines.append(f"## Period: {date_range}")
    lines.append(f"## Entries: {len(summaries)} summarized updates\n")

    by_agency: dict[str, list[dict]] = {}
    for s in summaries:
        agency = s.get("entry_agency", "Unknown")
        by_agency.setdefault(agency, []).append(s)

    for agency, items in sorted(by_agency.items()):
        lines.append(f"\n### {agency} ({len(items)} updates)\n")
        for item in items:
            lines.append(f"**{item.get('entry_title', 'Untitled')}**")
            lines.append(f"- Date: {item.get('entry_date', 'N/A')}")
            if item.get("what_happened"):
                lines.append(f"- What happened: {item['what_happened']}")
            if item.get("why_it_matters"):
                lines.append(f"- Why it matters: {item['why_it_matters']}")
            if item.get("action_needed"):
                lines.append(f"- Action needed: {item['action_needed']}")
            lines.append("")

    # --- Collect URL sources (non-LinkedIn, public regulatory) ---
    source_urls = []
    for entry in entries:
        link = entry.get("link")
        if link and link.startswith("http") and "linkedin.com" not in link:
            source_urls.append(link)
    source_urls = list(dict.fromkeys(source_urls))[:MAX_URL_SOURCES]

    # --- Find KB documents linked to digest entries ---
    kb_doc_ids = [
        entry["kb_doc_id"]
        for entry in entries
        if entry.get("kb_doc_id") and entry.get("download_status") == "downloaded"
    ]
    kb_docs = get_kb_documents_for_entries(kb_doc_ids)

    # Also get recent KB documents not directly linked to digests
    recent_docs = get_recent_kb_documents(days=days)
    seen_ids = set(kb_doc_ids)
    for doc in recent_docs:
        if doc["id"] not in seen_ids:
            kb_docs.append(doc)
            seen_ids.add(doc["id"])

    # Prefer original PDFs over extracted markdown (higher fidelity for NotebookLM)
    kb_paths = []
    for doc in kb_docs[:MAX_KB_DOCUMENTS]:
        pdf = doc.get("file_path")
        extracted = doc.get("extracted_path")
        if pdf and Path(pdf).exists():
            kb_paths.append(pdf)
        elif extracted and Path(extracted).exists():
            kb_paths.append(extracted)

    # --- Generate targeted research queries ---
    research_queries = generate_research_queries(summaries)

    return DigestExport(
        title=NOTEBOOK_TITLE_TEMPLATE.format(date_range=date_range),
        date_range=date_range,
        summary_text="\n".join(lines),
        entry_count=len(summaries),
        source_urls=source_urls,
        kb_document_paths=kb_paths,
        research_queries=research_queries,
    )


def export_digest(days: int = 7) -> DigestExport:
    """Export the latest digest for NotebookLM consumption."""
    summaries = get_recent_summaries(days)
    entries = get_recent_digest_entries(days)

    if not summaries and not entries:
        logger.info("No digest data found for the last %d days", days)
        now = datetime.now()
        start = now - timedelta(days=days)
        date_range = f"{start.strftime('%d %b')} – {now.strftime('%d %b %Y')}"
        return DigestExport(
            title=NOTEBOOK_TITLE_TEMPLATE.format(date_range=date_range),
            date_range=date_range,
            summary_text=f"# DLSC Regulatory Intelligence Digest\n\nNo updates for period {date_range}.",
            entry_count=0,
        )

    export = format_digest_for_notebooklm(summaries, entries, days)
    logger.info(
        "Exported digest: %d summaries, %d URLs, %d KB docs, %d research queries",
        export.entry_count,
        len(export.source_urls),
        len(export.kb_document_paths),
        len(export.research_queries),
    )
    return export


def create_digest_notebook(
    days: int = 7,
    title: str | None = None,
    skip_research: bool = False,
) -> nlm.NotebookLMResult:
    """Create a NotebookLM notebook with hybrid sources.

    Three source layers:
    1. Text digest summary (always)
    2. Local KB documents — extracted markdown or PDFs (if available)
    3. Targeted deep research queries (unless --skip-research)
    """
    export = export_digest(days)
    notebook_title = title or export.title

    print(f"Creating notebook: {notebook_title}")
    print(f"  Digest entries: {export.entry_count}")
    print(f"  URL sources: {len(export.source_urls)}")
    print(f"  KB documents: {len(export.kb_document_paths)}")
    print(f"  Research queries: {len(export.research_queries)}")

    # --- Layer 1: Create notebook with text digest ---
    create_result, source_results = nlm.create_notebook_with_sources(
        title=notebook_title,
        urls=export.source_urls,
        text_sources={"Regulatory Digest": export.summary_text},
    )

    if not create_result.success:
        print(f"ERROR: Failed to create notebook: {create_result.error}")
        return create_result

    notebook_id = create_result.data.get("id", "")
    print(f"  Notebook ID: {notebook_id}")

    url_succeeded = sum(1 for r in source_results if r.success)
    print(f"  URL + text sources: {url_succeeded}/{len(source_results)}")

    # --- Layer 2: Add KB documents ---
    kb_added = 0
    for doc_path in export.kb_document_paths:
        result = nlm.add_source(doc_path, notebook_id=notebook_id)
        if result.success:
            kb_added += 1
            doc_title = result.data.get("title", Path(doc_path).name)
            print(f"  KB doc added: {doc_title}")
        else:
            logger.warning("Failed to add KB doc %s: %s", doc_path, result.error)
    print(f"  KB documents added: {kb_added}/{len(export.kb_document_paths)}")

    # --- Layer 3: Targeted research ---
    if not skip_research and export.research_queries:
        for query in export.research_queries:
            print(f"  Research: '{query[:60]}...'")
            result = nlm.add_research(
                query,
                mode="deep",
                notebook_id=notebook_id,
                no_wait=True,
            )
            if result.success:
                print("    Started (background)")
            else:
                print(f"    Failed: {result.error}")
        print("  Research running in background — use 'notebooklm research status' to check")
    elif skip_research:
        print("  Research: skipped (--skip-research)")

    # Summary
    total_sources = url_succeeded + kb_added
    print(f"\n  Total sources added: {total_sources}")
    print(f"  Research queries launched: {0 if skip_research else len(export.research_queries)}")

    return create_result


def generate_content(
    artifact_type: str = "audio",
    instruction: str = "",
    notebook_id: str | None = None,
) -> nlm.NotebookLMResult:
    """Generate content from the current notebook."""
    default_instructions = {
        "audio": (
            "Create a regulatory update podcast episode for medical device professionals. "
            "Cover the most important updates first, explain why each matters for compliance, "
            "and highlight any required actions. Conversational but authoritative tone."
        ),
        "report": (
            "Create a briefing document summarizing the key regulatory updates. "
            "Organize by jurisdiction (EU, FDA, UK). Include action items."
        ),
        "data-table": (
            "Create a comparison table of all regulatory updates with columns: "
            "Agency, Title, Date, Impact Level (High/Medium/Low), Action Required."
        ),
        "mind-map": "",
        "quiz": "",
    }

    instr = instruction or default_instructions.get(artifact_type, "")
    print(f"Generating {artifact_type}...")

    result = nlm.generate_artifact(
        artifact_type,
        instr,
        notebook_id=notebook_id,
    )

    if result.success:
        task_id = result.data.get("task_id", "")
        print(f"  Generation started: task_id={task_id}")
        print(f"  Use 'notebooklm artifact wait {task_id}' to check status")
    else:
        print(f"  ERROR: {result.error}")

    return result


# --- Full Pipeline ---


def run_pipeline(
    days: int = 7,
    title: str | None = None,
    skip_research: bool = False,
    artifact_types: list[str] | None = None,
    repurpose: bool = False,
) -> list[nlm.ArtifactResult]:
    """Full pipeline: create notebook → add sources → generate → download → vault.

    Args:
        days: Days to look back for digest data.
        title: Override notebook title.
        skip_research: Skip deep web research.
        artifact_types: Which artifacts to generate (default: ["report"]).
        repurpose: Feed report into AIfirst content pipeline if available.

    Returns:
        List of ArtifactResult for each generated artifact.
    """
    if not nlm.check_auth():
        return []

    artifact_types = artifact_types or ["report"]

    # Step 1: Create notebook with all sources
    create_result = create_digest_notebook(days, title, skip_research)
    if not create_result.success:
        return []

    notebook_id = create_result.data.get("id", "")
    notebook_title = title or create_result.data.get("title", "DLSC Regulatory Update")

    # Step 2: Default instructions per artifact type
    default_instructions = {
        "audio": (
            "Create a regulatory update podcast episode for medical device professionals. "
            "Cover the most important updates first, explain why each matters for compliance, "
            "and highlight any required actions. Conversational but authoritative tone."
        ),
        "report": (
            "Create a briefing document summarizing the key regulatory updates. "
            "Organize by jurisdiction (EU, FDA, UK). Include action items."
        ),
        "data-table": (
            "Create a comparison table of all regulatory updates with columns: "
            "Agency, Title, Date, Impact Level (High/Medium/Low), Action Required."
        ),
    }

    default_formats = {
        "report": "briefing-doc",
        "audio": "deep-dive",
    }

    # Step 3: Batch generate
    date = nlm.vault_writer.today_prefix()
    results = nlm.batch_generate(
        artifact_types,
        instructions=default_instructions,
        notebook_id=notebook_id,
        formats=default_formats,
        output_dir=str(REGKB_ROOT / "downloads" / "notebooklm"),
        title_template=f"DLSC Regulatory Update - {date} - {{type}}",
        notebook_title=notebook_title,
        use_case="regulatory-intel",
        business="donlonlsc",
        extra_frontmatter={"generated_by": "notebooklm_export"},
    )

    # Step 4: Optional AIfirst content repurposing
    if repurpose:
        _repurpose_report(results)

    return results


def _repurpose_report(results: list[nlm.ArtifactResult]) -> None:
    """Feed downloaded report into AIfirst content pipeline if available."""
    report_results = [r for r in results if r.success and r.artifact_type == "report"]
    if not report_results:
        return

    try:
        from AIfirst.agents.content_pipeline.writer import write_all_formats
    except ImportError:
        print("  AIfirst content pipeline not available -- skipping repurpose")
        return

    for r in report_results:
        print(f"  Repurposing report: {r.download_path}")
        try:
            content = Path(r.download_path).read_text(encoding="utf-8")
            write_all_formats(content, source="notebooklm-regulatory-intel")
            print("  Content repurposed to vault/content/")
        except Exception as e:
            print(f"  Repurpose failed: {e}")


def download_artifact_cmd(
    artifact_type: str,
    notebook_id: str | None = None,
) -> nlm.ArtifactResult:
    """Download the latest artifact of a given type and save to vault.

    Args:
        artifact_type: audio, report, data-table, etc.
        notebook_id: Optional notebook ID.

    Returns:
        ArtifactResult with download and vault paths.
    """
    if not nlm.check_auth():
        return nlm.ArtifactResult(success=False, error="Auth failed")

    date = nlm.vault_writer.today_prefix()
    return nlm.generate_download_and_save(
        artifact_type,
        notebook_id=notebook_id,
        output_dir=str(REGKB_ROOT / "downloads" / "notebooklm"),
        title=f"DLSC Regulatory Update - {date} - {artifact_type}",
        notebook_title="DLSC Regulatory Update",
        use_case="regulatory-intel",
        business="donlonlsc",
        extra_frontmatter={"generated_by": "notebooklm_export"},
        # Skip generation — just download + vault
        poll_interval=5,
        max_wait=30,
    )


# --- CLI ---


def main():
    parser = argparse.ArgumentParser(
        description="NotebookLM export for RegulatoryKB intelligence pipeline",
        prog="python -m regkb.notebooklm_export",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # export-digest
    p_export = subparsers.add_parser("export-digest", help="Export digest as formatted text")
    p_export.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    p_export.add_argument("--output", type=str, help="Save to file instead of stdout")

    # create-notebook
    p_create = subparsers.add_parser(
        "create-notebook", help="Create NotebookLM notebook from digest"
    )
    p_create.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    p_create.add_argument("--title", type=str, help="Override notebook title")
    p_create.add_argument(
        "--skip-research",
        action="store_true",
        help="Skip deep web research (only use digest + KB docs)",
    )

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate content from current notebook")
    p_gen.add_argument(
        "type", choices=["audio", "report", "data-table", "quiz", "mind-map", "flashcards"]
    )
    p_gen.add_argument("--instruction", type=str, default="", help="Custom generation instruction")
    p_gen.add_argument("--notebook", type=str, help="Notebook ID")

    # run-pipeline (Phase 2)
    p_pipe = subparsers.add_parser(
        "run-pipeline",
        help="Full pipeline: create → add sources → generate → download → vault",
    )
    p_pipe.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    p_pipe.add_argument("--title", type=str, help="Override notebook title")
    p_pipe.add_argument("--skip-research", action="store_true", help="Skip deep web research")
    p_pipe.add_argument(
        "--types",
        type=str,
        default="report",
        help="Comma-separated artifact types (default: report)",
    )
    p_pipe.add_argument(
        "--repurpose",
        action="store_true",
        help="Feed report into AIfirst content pipeline",
    )

    # download (Phase 2)
    p_dl = subparsers.add_parser("download", help="Download latest artifact + save to vault")
    p_dl.add_argument(
        "type", choices=["audio", "report", "data-table", "quiz", "mind-map", "flashcards"]
    )
    p_dl.add_argument("--notebook", type=str, help="Notebook ID")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.command == "export-digest":
        export = export_digest(args.days)
        if args.output:
            Path(args.output).write_text(export.summary_text, encoding="utf-8")
            print(f"Exported to {args.output} ({export.entry_count} entries)")
        else:
            print(export.summary_text)

    elif args.command == "create-notebook":
        create_digest_notebook(args.days, args.title, args.skip_research)

    elif args.command == "generate":
        generate_content(args.type, args.instruction, args.notebook)

    elif args.command == "run-pipeline":
        types = [t.strip() for t in args.types.split(",")]
        results = run_pipeline(
            days=args.days,
            title=args.title,
            skip_research=args.skip_research,
            artifact_types=types,
            repurpose=args.repurpose,
        )
        ok = sum(1 for r in results if r.success)
        print(f"\nPipeline complete: {ok}/{len(results)} artifacts generated")

    elif args.command == "download":
        result = download_artifact_cmd(args.type, args.notebook)
        if result.success:
            print(f"Downloaded: {result.download_path}")
            if result.vault_path:
                print(f"Vault note: {result.vault_path}")
        else:
            print(f"Failed: {result.error}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
