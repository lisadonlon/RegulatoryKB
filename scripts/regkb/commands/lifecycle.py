"""Lifecycle and operations top-level CLI commands."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from tqdm import tqdm

from regkb.acquisition_list import export_acquisition_csv, get_acquisition_list_flat
from regkb.config import config
from regkb.gap_analysis import export_gap_report_csv, get_gap_summary, print_gap_report, run_gap_analysis
from regkb.services import get_db, get_downloader, get_extractor, get_importer, get_search_engine
from regkb.version_tracker import (
    check_all_versions,
    export_version_report_csv,
    get_version_summary,
    print_version_report,
)

logger = logging.getLogger(__name__)


def register_lifecycle_commands(cli: click.Group) -> None:
    """Register lifecycle/ops top-level commands on the main CLI group."""
    cli.add_command(import_docs)
    cli.add_command(ingest)
    cli.add_command(reindex)
    cli.add_command(extract)
    cli.add_command(ocr_reextract)
    cli.add_command(diff_cmd)
    cli.add_command(backup)
    cli.add_command(gap_analysis)
    cli.add_command(download_docs)
    cli.add_command(acquisition_list)
    cli.add_command(version_check)
    cli.add_command(web)


def _get_search_engine():
    return get_search_engine()


@click.command("import-docs")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option("-r", "--recursive", is_flag=True, default=True, help="Scan subdirectories")
@click.option("--no-recursive", is_flag=True, help="Don't scan subdirectories")
@click.option("-i", "--interactive", is_flag=True, help="Prompt for metadata for each file")
def import_docs(source: Path, recursive: bool, no_recursive: bool, interactive: bool) -> None:
    """Import PDF documents from a directory."""
    importer = get_importer()

    if no_recursive:
        recursive = False

    click.echo(f"Scanning {source} for PDF files...")
    metadata_callback = _interactive_metadata if interactive else None

    result = importer.import_directory(
        source,
        recursive=recursive,
        metadata_callback=metadata_callback,
        progress=True,
    )

    click.echo()
    click.echo(click.style(str(result), fg="green" if result.errors == 0 else "yellow"))

    if result.error_details:
        click.echo(click.style("\nErrors:", fg="red"))
        for error in result.error_details[:5]:
            click.echo(f"  - {error['file']}: {error['error']}")
        if len(result.error_details) > 5:
            click.echo(f"  ... and {len(result.error_details) - 5} more errors")


def _interactive_metadata(file_path: Path) -> dict:
    """Prompt user for metadata interactively."""
    click.echo(f"\n--- {file_path.name} ---")

    title = click.prompt("Title", default=file_path.stem.replace("_", " "))

    doc_types = config.document_types
    click.echo(f"Document types: {', '.join(f'{i}={t}' for i, t in enumerate(doc_types))}")
    type_idx = click.prompt("Document type", type=int, default=len(doc_types) - 1)
    document_type = doc_types[type_idx] if 0 <= type_idx < len(doc_types) else "other"

    jurisdictions = config.jurisdictions
    click.echo(f"Jurisdictions: {', '.join(f'{i}={j}' for i, j in enumerate(jurisdictions))}")
    jur_idx = click.prompt("Jurisdiction", type=int, default=len(jurisdictions) - 1)
    jurisdiction = jurisdictions[jur_idx] if 0 <= jur_idx < len(jurisdictions) else "Other"

    version = click.prompt("Version", default="", show_default=False) or None
    source_url = click.prompt("Source URL", default="", show_default=False) or None
    description = click.prompt("Description", default="", show_default=False) or None

    return {
        "title": title,
        "document_type": document_type,
        "jurisdiction": jurisdiction,
        "version": version,
        "source_url": source_url,
        "description": description,
    }


@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would be imported without importing")
@click.option(
    "--delete",
    is_flag=True,
    help="Delete files after successful import (default: move to processed/)",
)
def ingest(dry_run: bool, delete: bool) -> None:
    """Auto-import PDFs from the pending inbox folder."""
    importer = get_importer()
    pending_dir = config.pending_dir
    processed_dir = pending_dir / "processed"

    if not pending_dir.exists():
        click.echo(f"Creating pending folder structure at {pending_dir}")
        pending_dir.mkdir(parents=True, exist_ok=True)
        for doc_type in config.document_types:
            (pending_dir / doc_type).mkdir(exist_ok=True)
        processed_dir.mkdir(exist_ok=True)
        click.echo(
            "Folder structure created. Drop PDFs into subfolders and run 'regkb ingest' again."
        )
        return

    pdf_files = list(pending_dir.glob("**/*.pdf"))
    pdf_files = [f for f in pdf_files if "processed" not in f.parts]

    if not pdf_files:
        click.echo("No PDFs found in pending folder.")
        return

    click.echo(f"Found {len(pdf_files)} PDF(s) to import")

    imported = 0
    skipped = 0
    errors = []

    for pdf_path in pdf_files:
        rel_path = pdf_path.relative_to(pending_dir)
        parts = rel_path.parts[:-1]

        doc_type = "other"
        jurisdiction = "Other"

        if len(parts) >= 1:
            potential_type = parts[0].lower()
            if potential_type in [t.lower() for t in config.document_types]:
                doc_type = config.normalize_document_type(potential_type)

        if len(parts) >= 2:
            potential_jur = parts[1]
            if potential_jur.lower() in [j.lower() for j in config.jurisdictions]:
                jurisdiction = config.normalize_jurisdiction(potential_jur)

        metadata = {
            "document_type": doc_type,
            "jurisdiction": jurisdiction,
        }

        if dry_run:
            click.echo(
                f"  [DRY RUN] {pdf_path.name} -> type={doc_type}, jurisdiction={jurisdiction}"
            )
            continue

        try:
            doc_id = importer.import_file(pdf_path, metadata)
            if doc_id:
                click.echo(click.style(f"  + {pdf_path.name} (ID: {doc_id})", fg="green"))
                imported += 1

                if importer.last_content_warning:
                    click.echo(
                        click.style(
                            f"    !! {importer.last_content_warning}",
                            fg="yellow",
                        )
                    )

                vdiff = importer.last_version_diff
                if vdiff:
                    if vdiff.auto_superseded:
                        click.echo(
                            click.style(
                                f"    -> Supersedes [{vdiff.old_doc_id}] {vdiff.old_doc_title} "
                                f"(similarity: {vdiff.stats.similarity:.0%})",
                                fg="cyan",
                            )
                        )
                    else:
                        click.echo(
                            click.style(
                                f"    !! Possible match [{vdiff.old_doc_id}] {vdiff.old_doc_title} "
                                f"(similarity: {vdiff.stats.similarity:.0%}) — NOT auto-superseded",
                                fg="yellow",
                            )
                        )
                    if vdiff.diff_html_path:
                        click.echo(f"       Diff: {vdiff.diff_html_path}")

                if delete:
                    pdf_path.unlink()
                else:
                    processed_dir.mkdir(parents=True, exist_ok=True)
                    dest = processed_dir / pdf_path.name
                    counter = 1
                    while dest.exists():
                        dest = processed_dir / f"{pdf_path.stem}_{counter}{pdf_path.suffix}"
                        counter += 1
                    pdf_path.rename(dest)
            else:
                click.echo(click.style(f"  - {pdf_path.name} (duplicate or invalid)", fg="yellow"))
                skipped += 1
        except Exception as e:
            click.echo(click.style(f"  x {pdf_path.name}: {e}", fg="red"))
            errors.append({"file": pdf_path.name, "error": str(e)})

    if not dry_run:
        click.echo()
        click.echo(f"Imported: {imported}, Skipped: {skipped}, Errors: {len(errors)}")


@click.command()
def reindex() -> None:
    """Reindex all documents for search."""
    click.echo("Reindexing all documents...")

    with tqdm(total=100, desc="Indexing") as pbar:

        def progress(current: int, total: int) -> None:
            pbar.total = total
            pbar.n = current
            pbar.refresh()

        count = _get_search_engine().reindex_all(progress_callback=progress)

    click.echo(click.style(f"\nIndexed {count} documents", fg="green"))


@click.command()
@click.argument("doc_id", type=int)
@click.option("--ocr", is_flag=True, help="Force OCR on all pages (requires Tesseract)")
def extract(doc_id: int, ocr: bool) -> None:
    """Re-extract text from a document's PDF."""
    db = get_db()
    extractor = get_extractor()
    doc = db.get_document(doc_id=doc_id)

    if not doc:
        click.echo(click.style(f"Document not found: {doc_id}", fg="red"))
        sys.exit(1)

    pdf_path = Path(doc["file_path"])
    if not pdf_path.exists():
        click.echo(click.style(f"PDF file not found: {pdf_path}", fg="red"))
        sys.exit(1)

    if ocr:
        from regkb.extraction import _check_ocr_available

        if not _check_ocr_available():
            click.echo(
                click.style(
                    "OCR not available. Install Tesseract and run: pip install regkb[ocr]",
                    fg="red",
                )
            )
            sys.exit(1)
        click.echo(f"Re-extracting text (with forced OCR) from {pdf_path.name}...")
    else:
        click.echo(f"Re-extracting text from {pdf_path.name}...")

    success, output_path, error = extractor.re_extract(pdf_path, doc_id, force_ocr=ocr)

    if success:
        db.update_document(doc_id, extracted_path=str(output_path))
        click.echo(click.style(f"Extracted to: {output_path}", fg="green"))
    else:
        click.echo(click.style(f"Extraction failed: {error}", fg="red"))


@click.command("ocr-reextract")
@click.option("--doc-id", type=int, default=None, help="Re-extract a single document by ID")
@click.option("--all", "all_docs", is_flag=True, help="Re-extract all documents with OCR")
def ocr_reextract(doc_id: int, all_docs: bool) -> None:
    """Batch re-extract documents using OCR."""
    from regkb.extraction import _check_ocr_available

    db = get_db()
    extractor = get_extractor()

    if not _check_ocr_available():
        click.echo(
            click.style(
                "OCR not available. Install Tesseract and run: pip install regkb[ocr]",
                fg="red",
            )
        )
        sys.exit(1)

    if not doc_id and not all_docs:
        click.echo(click.style("Provide --doc-id <id> or --all", fg="red"))
        sys.exit(1)

    if doc_id:
        doc = db.get_document(doc_id=doc_id)
        if not doc:
            click.echo(click.style(f"Document not found: {doc_id}", fg="red"))
            sys.exit(1)
        docs = [doc]
    else:
        docs = db.list_documents(latest_only=False, limit=10000)
        if not docs:
            click.echo("No documents in the knowledge base.")
            return

    success_count = 0
    fail_count = 0
    for doc in tqdm(docs, desc="OCR re-extracting", disable=len(docs) == 1):
        pdf_path = Path(doc["file_path"])
        if not pdf_path.exists():
            click.echo(click.style(f"  PDF not found for doc {doc['id']}: {pdf_path}", fg="yellow"))
            fail_count += 1
            continue

        ok, out_path, err = extractor.re_extract(pdf_path, doc["id"], force_ocr=True)
        if ok:
            db.update_document(doc["id"], extracted_path=str(out_path))
            success_count += 1
        else:
            click.echo(click.style(f"  Failed doc {doc['id']}: {err}", fg="red"))
            fail_count += 1

    click.echo()
    click.echo(
        click.style(
            f"OCR re-extraction complete: {success_count} succeeded, {fail_count} failed",
            fg="green" if fail_count == 0 else "yellow",
        )
    )


@click.command("diff")
@click.argument("id1", type=int)
@click.argument("id2", type=int)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Save HTML side-by-side diff to file",
)
@click.option("--stats-only", is_flag=True, help="Show only summary statistics")
@click.option("--context", type=int, default=3, help="Number of context lines (default: 3)")
def diff_cmd(id1: int, id2: int, output: Optional[Path], stats_only: bool, context: int) -> None:
    """Compare two documents side-by-side."""
    from regkb.diff import compare_documents

    db = get_db()
    doc1 = db.get_document(doc_id=id1)
    doc2 = db.get_document(doc_id=id2)

    if not doc1:
        click.echo(click.style(f"Document not found: {id1}", fg="red"))
        sys.exit(1)
    if not doc2:
        click.echo(click.style(f"Document not found: {id2}", fg="red"))
        sys.exit(1)

    title1 = doc1.get("title", f"Document {id1}")
    title2 = doc2.get("title", f"Document {id2}")

    result = compare_documents(
        doc1_id=id1,
        doc2_id=id2,
        doc1_title=title1,
        doc2_title=title2,
        context_lines=context,
        include_html=output is not None,
    )

    if result is None:
        click.echo(
            click.style(
                "Cannot compare: one or both documents have no extracted text. "
                "Run 'regkb extract <id>' first.",
                fg="red",
            )
        )
        sys.exit(1)

    click.echo(click.style("Document Comparison", fg="cyan", bold=True))
    click.echo(f"  A: [{id1}] {title1}")
    click.echo(f"  B: [{id2}] {title2}")
    click.echo()
    click.echo(result.stats.summary())

    if stats_only:
        return

    if result.unified_diff:
        click.echo()
        for line in result.unified_diff.splitlines():
            safe_line = line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8", errors="replace"
            )
            if safe_line.startswith("+++") or safe_line.startswith("---"):
                click.echo(click.style(safe_line, bold=True))
            elif safe_line.startswith("+"):
                click.echo(click.style(safe_line, fg="green"))
            elif safe_line.startswith("-"):
                click.echo(click.style(safe_line, fg="red"))
            elif safe_line.startswith("@@"):
                click.echo(click.style(safe_line, fg="cyan"))
            else:
                click.echo(safe_line)
    else:
        click.echo("\nDocuments are identical.")

    if output and result.html_diff:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.html_diff, encoding="utf-8")
        click.echo(click.style(f"\nHTML diff saved to: {output}", fg="green"))


@click.command()
def backup() -> None:
    """Create a backup of the database."""
    db = get_db()
    click.echo("Creating database backup...")
    backup_path = db.backup()
    click.echo(click.style(f"Backup created: {backup_path}", fg="green"))


@click.command("gaps")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction (EU, UK, US, etc.)")
@click.option("--mandatory-only", is_flag=True, help="Show only mandatory documents")
@click.option("--show-matched", is_flag=True, help="Also show matched documents")
@click.option("--export", "export_path", type=click.Path(), help="Export report to CSV")
def gap_analysis(
    jurisdiction: Optional[str],
    mandatory_only: bool,
    show_matched: bool,
    export_path: Optional[str],
) -> None:
    """Analyze gaps in the knowledge base against reference checklist."""
    click.echo("Running gap analysis...")

    db_path = str(config.database_path)
    results = run_gap_analysis(db_path)

    if jurisdiction:
        jurisdiction_upper = jurisdiction.upper()
        if jurisdiction_upper in results:
            results = {jurisdiction_upper: results[jurisdiction_upper]}
        else:
            click.echo(click.style(f"Unknown jurisdiction: {jurisdiction}", fg="red"))
            click.echo(f"Available: {', '.join(results.keys())}")
            return

    print_gap_report(results, show_matched=show_matched)

    if export_path:
        export_gap_report_csv(results, export_path)
        click.echo(click.style(f"\nReport exported to: {export_path}", fg="green"))

    summary = get_gap_summary(results)
    if mandatory_only:
        missing = summary["mandatory_missing"]
        click.echo(
            click.style(
                f"\n{missing} MANDATORY documents missing - prioritize these!",
                fg="red" if missing > 0 else "green",
            )
        )
    else:
        coverage = summary["overall_coverage"]
        color = "green" if coverage >= 80 else "yellow" if coverage >= 50 else "red"
        click.echo(click.style(f"\nOverall coverage: {coverage}%", fg=color))


@click.command("download")
@click.option("-j", "--jurisdiction", help="Download only this jurisdiction (EU, UK, US, etc.)")
@click.option(
    "--mandatory-only",
    is_flag=True,
    default=True,
    help="Download only mandatory documents (default)",
)
@click.option("--all", "download_all", is_flag=True, help="Download all documents including optional")
@click.option("--import/--no-import", "do_import", default=True, help="Import downloaded files to KB")
@click.option(
    "--delay",
    default=1.5,
    type=click.FloatRange(0.0, 60.0),
    help="Delay between downloads (0-60 seconds)",
)
def download_docs(
    jurisdiction: Optional[str],
    mandatory_only: bool,
    download_all: bool,
    do_import: bool,
    delay: float,
) -> None:
    """Download regulatory documents from official sources."""
    downloader = get_downloader()
    importer = get_importer()
    docs = get_acquisition_list_flat()

    docs = [d for d in docs if d.get("free", True)]

    if jurisdiction:
        jurisdiction_upper = jurisdiction.upper()
        docs = [d for d in docs if d["jurisdiction"].upper() == jurisdiction_upper]

    if not download_all:
        docs = [d for d in docs if d.get("mandatory", False)]

    if not docs:
        click.echo("No documents to download with current filters.")
        return

    click.echo(click.style(f"\nDownloading {len(docs)} documents...\n", fg="bright_white", bold=True))

    def progress(current, total, message):
        click.echo(f"[{current}/{total}] {message}")

    results = downloader.download_batch(docs, progress_callback=progress, delay=delay)

    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(click.style("DOWNLOAD SUMMARY", fg="bright_white", bold=True))
    click.echo(click.style(f"{'=' * 50}", fg="cyan"))
    click.echo(f"  Downloaded: {len(results['success'])}")
    click.echo(f"  Failed:     {len(results['failed'])}")
    click.echo(f"  Skipped:    {len(results['skipped'])} (web pages - manual download)")

    if results["failed"]:
        click.echo(click.style("\nFailed downloads:", fg="red"))
        for f in results["failed"][:10]:
            click.echo(f"  - {f['title']}: {f['error']}")

    if results["skipped"]:
        click.echo(click.style("\nSkipped (manual download required):", fg="yellow"))
        for s in results["skipped"][:10]:
            click.echo(f"  - {s['title']}")
            click.echo(f"    {s['url']}")

    if do_import and results["success"]:
        click.echo(click.style("\nImporting downloaded documents...", fg="cyan"))
        imported = 0
        for doc in results["success"]:
            file_path = Path(doc["file_path"])
            if file_path.exists():
                metadata = {
                    "title": doc["title"],
                    "jurisdiction": doc["jurisdiction"],
                    "document_type": "guidance"
                    if "guidance" in doc.get("category", "")
                    else "regulation",
                    "source_url": doc["url"],
                }
                doc_id = importer.import_file(file_path, metadata)
                if doc_id:
                    imported += 1

        click.echo(click.style(f"Imported {imported} documents to knowledge base", fg="green"))

        if imported > 0:
            click.echo("Reindexing search...")
            _get_search_engine().reindex_all()
            click.echo(click.style("Reindex complete", fg="green"))


@click.command("acquire")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction (EU, UK, US, etc.)")
@click.option("--mandatory-only", is_flag=True, help="Show only mandatory documents")
@click.option("--free-only", is_flag=True, help="Show only free documents")
@click.option("--export", "export_path", type=click.Path(), help="Export list to CSV")
def acquisition_list(
    jurisdiction: Optional[str],
    mandatory_only: bool,
    free_only: bool,
    export_path: Optional[str],
) -> None:
    """Show list of recommended documents to acquire with download URLs."""
    docs = get_acquisition_list_flat()

    if jurisdiction:
        jurisdiction_upper = jurisdiction.upper()
        docs = [d for d in docs if d["jurisdiction"].upper() == jurisdiction_upper]
    if mandatory_only:
        docs = [d for d in docs if d.get("mandatory", False)]
    if free_only:
        docs = [d for d in docs if d.get("free", True)]

    if not docs:
        click.echo("No documents match the specified filters.")
        return

    if export_path:
        export_acquisition_csv(export_path, mandatory_only=mandatory_only, free_only=free_only)
        click.echo(click.style(f"Acquisition list exported to: {export_path}", fg="green"))
        return

    click.echo(click.style("\nREGULATORY DOCUMENT ACQUISITION LIST", fg="bright_white", bold=True))
    click.echo("=" * 60)

    current_jur = None
    free_count = 0
    paid_count = 0

    for doc in docs:
        if doc["jurisdiction"] != current_jur:
            current_jur = doc["jurisdiction"]
            click.echo(click.style(f"\n--- {current_jur} ---", fg="cyan", bold=True))

        mandatory = click.style("[MANDATORY]", fg="red") if doc.get("mandatory") else ""
        if doc.get("free", True):
            free_tag = click.style("[FREE]", fg="green")
            free_count += 1
        else:
            price = doc.get("price_approx", "PAID")
            free_tag = click.style(f"[{price}]", fg="yellow")
            paid_count += 1

        click.echo(f"\n  {doc['title']} {mandatory} {free_tag}")
        click.echo(f"  {doc['description']}")
        click.echo(click.style(f"  {doc['url']}", fg="blue"))

    click.echo(f"\n{'=' * 60}")
    click.echo(f"Total: {len(docs)} documents ({free_count} free, {paid_count} require purchase)")


@click.command("versions")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction (EU, UK, US, etc.)")
@click.option("--show-current", is_flag=True, help="Also show documents that are current")
@click.option("--export", "export_path", type=click.Path(), help="Export report to CSV")
def version_check(
    jurisdiction: Optional[str],
    show_current: bool,
    export_path: Optional[str],
) -> None:
    """Check if documents in the knowledge base are current versions."""
    click.echo("Checking document versions...")

    db_path = str(config.database_path)
    results = check_all_versions(db_path)

    if jurisdiction:
        jurisdiction_upper = jurisdiction.upper()
        results = [r for r in results if r.jurisdiction.upper() == jurisdiction_upper]

    if not results:
        click.echo("No documents found matching criteria.")
        return

    print_version_report(results, show_current=show_current)

    if export_path:
        export_version_report_csv(results, export_path)
        click.echo(click.style(f"\nReport exported to: {export_path}", fg="green"))

    summary = get_version_summary(results)
    outdated = summary["outdated"]
    if outdated > 0:
        click.echo(
            click.style(
                f"\n{outdated} document(s) may need updating - check URLs above",
                fg="yellow",
            )
        )


@click.command()
@click.option("--host", default="127.0.0.1", help="Host to bind")
@click.option("--port", default=8000, type=int, help="Port to bind")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def web(host: str, port: int, reload: bool) -> None:
    """Start the web interface."""
    try:
        import uvicorn
    except ImportError as err:
        click.echo(
            click.style(
                "Web dependencies not installed. Run: pip install -e '.[web]'",
                fg="red",
            )
        )
        raise SystemExit(1) from err

    click.echo(click.style(f"Starting web server at http://{host}:{port}", fg="green"))
    uvicorn.run("regkb.web.main:app", host=host, port=port, reload=reload)