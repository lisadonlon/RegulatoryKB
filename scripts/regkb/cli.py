"""
Command-line interface for the Regulatory Knowledge Base.

Provides commands for importing, searching, and managing regulatory documents.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from tqdm import tqdm

from . import __version__
from .config import config
from .database import db
from .extraction import extractor
from .importer import importer
from .search import search_engine
from .gap_analysis import run_gap_analysis, print_gap_report, get_gap_summary, export_gap_report_csv
from .acquisition_list import get_acquisition_list_flat, export_acquisition_csv, ACQUISITION_LIST
from .downloader import downloader
from .version_tracker import check_all_versions, print_version_report, get_version_summary, export_version_report_csv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def setup_file_logging() -> None:
    """Set up file logging if enabled."""
    if config.get("logging.file_enabled", True):
        log_file = config.logs_dir / "regkb.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter(config.get("logging.format"))
        )
        logging.getLogger().addHandler(file_handler)


@click.group()
@click.version_option(version=__version__, prog_name="regkb")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def cli(verbose: bool) -> None:
    """Regulatory Knowledge Base - Manage and search regulatory documents."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    setup_file_logging()


@cli.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option("-r", "--recursive", is_flag=True, default=True, help="Scan subdirectories")
@click.option("--no-recursive", is_flag=True, help="Don't scan subdirectories")
@click.option("-i", "--interactive", is_flag=True, help="Prompt for metadata for each file")
def import_docs(source: Path, recursive: bool, no_recursive: bool, interactive: bool) -> None:
    """
    Import PDF documents from a directory.

    SOURCE is the directory containing PDFs to import.
    """
    if no_recursive:
        recursive = False

    click.echo(f"Scanning {source} for PDF files...")

    if interactive:
        metadata_callback = _interactive_metadata
    else:
        metadata_callback = None

    result = importer.import_directory(
        source,
        recursive=recursive,
        metadata_callback=metadata_callback,
        progress=True
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


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option("-t", "--type", "doc_type", help="Filter by document type")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction")
@click.option("-n", "--limit", default=10, help="Maximum results")
@click.option("--all-versions", is_flag=True, help="Include older versions")
@click.option("--no-excerpt", is_flag=True, help="Don't show excerpts")
def search(
    query: tuple,
    doc_type: Optional[str],
    jurisdiction: Optional[str],
    limit: int,
    all_versions: bool,
    no_excerpt: bool,
) -> None:
    """
    Search for documents using natural language.

    QUERY is the search query (can be multiple words).
    """
    query_str = " ".join(query)
    click.echo(f"Searching for: {query_str}")

    try:
        results = search_engine.search(
            query_str,
            limit=limit,
            document_type=doc_type,
            jurisdiction=jurisdiction,
            latest_only=not all_versions,
            include_excerpt=not no_excerpt,
        )

        if not results:
            click.echo(click.style("No results found.", fg="yellow"))
            return

        click.echo(f"\nFound {len(results)} results:\n")

        for i, doc in enumerate(results, 1):
            score = doc.get("relevance_score", 0)
            click.echo(click.style(f"{i}. {doc['title']}", fg="bright_white", bold=True))
            click.echo(f"   Type: {doc['document_type']} | Jurisdiction: {doc['jurisdiction']}")
            click.echo(f"   Score: {score:.3f} | ID: {doc['id']}")
            click.echo(f"   Path: {doc['file_path']}")

            if doc.get("excerpt"):
                # Clean excerpt of problematic characters for Windows console
                excerpt = doc['excerpt'][:200].encode('ascii', 'replace').decode('ascii')
                click.echo(f"   Excerpt: {excerpt}")

            click.echo()

    except Exception as e:
        click.echo(click.style(f"Search failed: {e}", fg="red"))
        logger.exception("Search error")


@cli.command()
@click.argument("source", type=click.Path(path_type=Path))
@click.option("-t", "--title", help="Document title")
@click.option("--type", "doc_type", help="Document type")
@click.option("-j", "--jurisdiction", help="Jurisdiction")
@click.option("-v", "--version", "doc_version", help="Document version")
@click.option("-u", "--url", "source_url", help="Source URL")
@click.option("-d", "--description", help="Description")
def add(
    source: Path,
    title: Optional[str],
    doc_type: Optional[str],
    jurisdiction: Optional[str],
    doc_version: Optional[str],
    source_url: Optional[str],
    description: Optional[str],
) -> None:
    """
    Add a single document to the knowledge base.

    SOURCE can be a local file path or a URL.
    """
    # Check if source is a URL
    source_str = str(source)
    is_url = source_str.startswith("http://") or source_str.startswith("https://")

    # Build metadata
    metadata = {}
    if title:
        metadata["title"] = title
    if doc_type:
        metadata["document_type"] = doc_type
    if jurisdiction:
        metadata["jurisdiction"] = jurisdiction
    if doc_version:
        metadata["version"] = doc_version
    if source_url:
        metadata["source_url"] = source_url
    if description:
        metadata["description"] = description

    if is_url:
        click.echo(f"Downloading from {source_str}...")
        doc_id = importer.import_from_url(source_str, metadata if metadata else None)
    else:
        if not source.exists():
            click.echo(click.style(f"File not found: {source}", fg="red"))
            sys.exit(1)
        click.echo(f"Adding {source.name}...")
        doc_id = importer.import_file(source, metadata if metadata else None)

    if doc_id:
        click.echo(click.style(f"Document added successfully (ID: {doc_id})", fg="green"))
    else:
        click.echo(click.style("Document already exists or import failed", fg="yellow"))


@cli.command("list")
@click.option("-t", "--type", "doc_type", help="Filter by document type")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction")
@click.option("--all-versions", is_flag=True, help="Include older versions")
@click.option("-n", "--limit", default=20, help="Maximum results")
def list_docs(
    doc_type: Optional[str],
    jurisdiction: Optional[str],
    all_versions: bool,
    limit: int,
) -> None:
    """List documents in the knowledge base."""
    documents = db.list_documents(
        document_type=doc_type,
        jurisdiction=jurisdiction,
        latest_only=not all_versions,
        limit=limit,
    )

    if not documents:
        click.echo("No documents found.")
        return

    click.echo(f"Found {len(documents)} documents:\n")

    for doc in documents:
        latest_marker = "" if doc.get("is_latest") else " [older version]"
        click.echo(f"[{doc['id']}] {doc['title']}{latest_marker}")
        click.echo(f"     Type: {doc['document_type']} | Jurisdiction: {doc['jurisdiction']}")

    click.echo(f"\nShowing {len(documents)} of {db.get_statistics()['total_documents']} total")


@cli.command()
@click.argument("doc_id", type=int)
def show(doc_id: int) -> None:
    """Show detailed information about a document."""
    doc = db.get_document(doc_id=doc_id)

    if not doc:
        click.echo(click.style(f"Document not found: {doc_id}", fg="red"))
        sys.exit(1)

    click.echo(click.style(f"\n{doc['title']}", fg="bright_white", bold=True))
    click.echo("-" * 60)
    click.echo(f"ID:           {doc['id']}")
    click.echo(f"Type:         {doc['document_type']}")
    click.echo(f"Jurisdiction: {doc['jurisdiction']}")
    click.echo(f"Version:      {doc.get('version') or 'N/A'}")
    click.echo(f"Latest:       {'Yes' if doc.get('is_latest') else 'No'}")
    click.echo(f"Hash:         {doc['hash'][:16]}...")
    click.echo(f"Source URL:   {doc.get('source_url') or 'N/A'}")
    click.echo(f"File:         {doc['file_path']}")
    click.echo(f"Extracted:    {doc.get('extracted_path') or 'N/A'}")
    click.echo(f"Download:     {doc.get('download_date', 'N/A')}")
    click.echo(f"Imported:     {doc['import_date']}")

    if doc.get("description"):
        click.echo(f"\nDescription:\n{doc['description']}")


@cli.command()
@click.argument("doc_id", type=int)
@click.option("-t", "--title", help="New title")
@click.option("--type", "doc_type", help="New document type")
@click.option("-j", "--jurisdiction", help="New jurisdiction")
@click.option("-v", "--version", "doc_version", help="New version")
@click.option("-d", "--description", help="New description")
@click.option("--superseded-by", type=int, help="ID of document that supersedes this one")
def update(
    doc_id: int,
    title: Optional[str],
    doc_type: Optional[str],
    jurisdiction: Optional[str],
    doc_version: Optional[str],
    description: Optional[str],
    superseded_by: Optional[int],
) -> None:
    """Update metadata for a document."""
    updates = {}
    if title:
        updates["title"] = title
    if doc_type:
        updates["document_type"] = doc_type
    if jurisdiction:
        updates["jurisdiction"] = jurisdiction
    if doc_version:
        updates["version"] = doc_version
    if description:
        updates["description"] = description
    if superseded_by:
        updates["superseded_by"] = superseded_by
        updates["is_latest"] = False

    if not updates:
        click.echo("No updates specified. Use --help for options.")
        return

    if db.update_document(doc_id, **updates):
        click.echo(click.style(f"Document {doc_id} updated successfully", fg="green"))
    else:
        click.echo(click.style(f"Failed to update document {doc_id}", fg="red"))


@cli.command()
def stats() -> None:
    """Show knowledge base statistics."""
    stats = db.get_statistics()

    click.echo(click.style("\nRegulatory Knowledge Base Statistics", fg="bright_white", bold=True))
    click.echo("=" * 40)
    click.echo(f"Total documents:    {stats['total_documents']}")
    click.echo(f"Latest versions:    {stats['latest_versions']}")
    click.echo(f"Total imports:      {stats['total_imports']}")

    if stats.get("by_type"):
        click.echo("\nBy Document Type:")
        for doc_type, count in sorted(stats["by_type"].items()):
            click.echo(f"  {doc_type}: {count}")

    if stats.get("by_jurisdiction"):
        click.echo("\nBy Jurisdiction:")
        for jur, count in sorted(stats["by_jurisdiction"].items()):
            click.echo(f"  {jur}: {count}")


@cli.command()
def reindex() -> None:
    """Reindex all documents for search."""
    click.echo("Reindexing all documents...")

    with tqdm(total=100, desc="Indexing") as pbar:
        def progress(current: int, total: int) -> None:
            pbar.total = total
            pbar.n = current
            pbar.refresh()

        count = search_engine.reindex_all(progress_callback=progress)

    click.echo(click.style(f"\nIndexed {count} documents", fg="green"))


@cli.command()
@click.argument("doc_id", type=int)
def extract(doc_id: int) -> None:
    """Re-extract text from a document's PDF."""
    doc = db.get_document(doc_id=doc_id)

    if not doc:
        click.echo(click.style(f"Document not found: {doc_id}", fg="red"))
        sys.exit(1)

    pdf_path = Path(doc["file_path"])
    if not pdf_path.exists():
        click.echo(click.style(f"PDF file not found: {pdf_path}", fg="red"))
        sys.exit(1)

    click.echo(f"Re-extracting text from {pdf_path.name}...")
    success, output_path, error = extractor.re_extract(pdf_path, doc_id)

    if success:
        db.update_document(doc_id, extracted_path=str(output_path))
        click.echo(click.style(f"Extracted to: {output_path}", fg="green"))
    else:
        click.echo(click.style(f"Extraction failed: {error}", fg="red"))


@cli.command()
def backup() -> None:
    """Create a backup of the database."""
    click.echo("Creating database backup...")
    backup_path = db.backup()
    click.echo(click.style(f"Backup created: {backup_path}", fg="green"))


@cli.command("gaps")
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
    """
    Analyze gaps in the knowledge base against reference checklist.

    Shows which essential regulatory documents are missing from the KB.
    """
    click.echo("Running gap analysis...")

    db_path = str(config.database_path)
    results = run_gap_analysis(db_path)

    # Filter by jurisdiction if specified
    if jurisdiction:
        jurisdiction_upper = jurisdiction.upper()
        if jurisdiction_upper in results:
            results = {jurisdiction_upper: results[jurisdiction_upper]}
        else:
            click.echo(click.style(f"Unknown jurisdiction: {jurisdiction}", fg="red"))
            click.echo(f"Available: {', '.join(results.keys())}")
            return

    # Print report
    print_gap_report(results, show_matched=show_matched)

    # Export if requested
    if export_path:
        export_gap_report_csv(results, export_path)
        click.echo(click.style(f"\nReport exported to: {export_path}", fg="green"))

    # Summary
    summary = get_gap_summary(results)
    if mandatory_only:
        missing = summary["mandatory_missing"]
        click.echo(click.style(
            f"\n{missing} MANDATORY documents missing - prioritize these!",
            fg="red" if missing > 0 else "green"
        ))
    else:
        coverage = summary["overall_coverage"]
        color = "green" if coverage >= 80 else "yellow" if coverage >= 50 else "red"
        click.echo(click.style(f"\nOverall coverage: {coverage}%", fg=color))


@cli.command("download")
@click.option("-j", "--jurisdiction", help="Download only this jurisdiction (EU, UK, US, etc.)")
@click.option("--mandatory-only", is_flag=True, default=True, help="Download only mandatory documents (default)")
@click.option("--all", "download_all", is_flag=True, help="Download all documents including optional")
@click.option("--import/--no-import", "do_import", default=True, help="Import downloaded files to KB")
@click.option("--delay", default=1.5, help="Delay between downloads in seconds")
def download_docs(
    jurisdiction: Optional[str],
    mandatory_only: bool,
    download_all: bool,
    do_import: bool,
    delay: float,
) -> None:
    """
    Download regulatory documents from official sources.

    Downloads free documents from the acquisition list and optionally imports them.
    """
    docs = get_acquisition_list_flat()

    # Filter to free documents only
    docs = [d for d in docs if d.get("free", True)]

    # Filter by jurisdiction
    if jurisdiction:
        jurisdiction_upper = jurisdiction.upper()
        docs = [d for d in docs if d["jurisdiction"].upper() == jurisdiction_upper]

    # Filter mandatory
    if not download_all:
        docs = [d for d in docs if d.get("mandatory", False)]

    if not docs:
        click.echo("No documents to download with current filters.")
        return

    click.echo(click.style(f"\nDownloading {len(docs)} documents...\n", fg="bright_white", bold=True))

    def progress(current, total, message):
        click.echo(f"[{current}/{total}] {message}")

    results = downloader.download_batch(docs, progress_callback=progress, delay=delay)

    # Summary
    click.echo(click.style(f"\n{'='*50}", fg="cyan"))
    click.echo(click.style("DOWNLOAD SUMMARY", fg="bright_white", bold=True))
    click.echo(click.style(f"{'='*50}", fg="cyan"))
    click.echo(f"  Downloaded: {len(results['success'])}")
    click.echo(f"  Failed:     {len(results['failed'])}")
    click.echo(f"  Skipped:    {len(results['skipped'])} (web pages - manual download)")

    # Show failures
    if results['failed']:
        click.echo(click.style("\nFailed downloads:", fg="red"))
        for f in results['failed'][:10]:
            click.echo(f"  - {f['title']}: {f['error']}")

    # Show skipped
    if results['skipped']:
        click.echo(click.style("\nSkipped (manual download required):", fg="yellow"))
        for s in results['skipped'][:10]:
            click.echo(f"  - {s['title']}")
            click.echo(f"    {s['url']}")

    # Import downloaded files
    if do_import and results['success']:
        click.echo(click.style("\nImporting downloaded documents...", fg="cyan"))
        imported = 0
        for doc in results['success']:
            file_path = Path(doc['file_path'])
            if file_path.exists():
                metadata = {
                    'title': doc['title'],
                    'jurisdiction': doc['jurisdiction'],
                    'document_type': 'guidance' if 'guidance' in doc.get('category', '') else 'regulation',
                    'source_url': doc['url'],
                }
                doc_id = importer.import_file(file_path, metadata)
                if doc_id:
                    imported += 1

        click.echo(click.style(f"Imported {imported} documents to knowledge base", fg="green"))

        # Reindex
        if imported > 0:
            click.echo("Reindexing search...")
            search_engine.reindex_all()
            click.echo(click.style("Reindex complete", fg="green"))


@cli.command("acquire")
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
    """
    Show list of recommended documents to acquire with download URLs.

    Use this to fill gaps identified by the 'gaps' command.
    """
    docs = get_acquisition_list_flat()

    # Apply filters
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

    # Export if requested
    if export_path:
        export_acquisition_csv(export_path, mandatory_only=mandatory_only, free_only=free_only)
        click.echo(click.style(f"Acquisition list exported to: {export_path}", fg="green"))
        return

    # Print list
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

    click.echo(f"\n{'='*60}")
    click.echo(f"Total: {len(docs)} documents ({free_count} free, {paid_count} require purchase)")


@cli.command("versions")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction (EU, UK, US, etc.)")
@click.option("--show-current", is_flag=True, help="Also show documents that are current")
@click.option("--export", "export_path", type=click.Path(), help="Export report to CSV")
def version_check(
    jurisdiction: Optional[str],
    show_current: bool,
    export_path: Optional[str],
) -> None:
    """
    Check if documents in the knowledge base are current versions.

    Compares documents against known latest versions and identifies outdated ones.
    """
    click.echo("Checking document versions...")

    db_path = str(config.database_path)
    results = check_all_versions(db_path)

    # Filter by jurisdiction if specified
    if jurisdiction:
        jurisdiction_upper = jurisdiction.upper()
        results = [r for r in results if r.jurisdiction.upper() == jurisdiction_upper]

    if not results:
        click.echo("No documents found matching criteria.")
        return

    # Print report
    print_version_report(results, show_current=show_current)

    # Export if requested
    if export_path:
        export_version_report_csv(results, export_path)
        click.echo(click.style(f"\nReport exported to: {export_path}", fg="green"))

    # Summary with color coding
    summary = get_version_summary(results)
    outdated = summary["outdated"]
    if outdated > 0:
        click.echo(click.style(
            f"\n{outdated} document(s) may need updating - check URLs above",
            fg="yellow"
        ))


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
