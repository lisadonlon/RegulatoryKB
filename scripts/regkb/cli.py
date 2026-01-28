"""
Command-line interface for the Regulatory Knowledge Base.

Provides commands for importing, searching, and managing regulatory documents.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables from .env file (if it exists)
load_dotenv()

from . import __version__
from .acquisition_list import export_acquisition_csv, get_acquisition_list_flat
from .config import config
from .database import db
from .downloader import downloader
from .extraction import extractor
from .gap_analysis import export_gap_report_csv, get_gap_summary, print_gap_report, run_gap_analysis
from .importer import importer
from .intelligence.analyzer import analyzer as kb_analyzer
from .intelligence.digest_tracker import digest_tracker
from .intelligence.emailer import emailer as intel_emailer
from .intelligence.fetcher import fetcher as newsletter_fetcher
from .intelligence.filter import FilterResult, content_filter
from .intelligence.reply_handler import reply_handler
from .intelligence.scheduler import (
    generate_batch_script,
    generate_imap_batch_script,
    generate_windows_task_xml,
    scheduler_state,
)
from .intelligence.summarizer import summarizer as intel_summarizer
from .intelligence.url_resolver import url_resolver
from .search import search_engine
from .version_tracker import (
    check_all_versions,
    export_version_report_csv,
    get_version_summary,
    print_version_report,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def setup_file_logging() -> None:
    """Set up file logging if enabled."""
    if config.get("logging.file_enabled", True):
        log_file = config.logs_dir / "regkb.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(config.get("logging.format")))
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
        source, recursive=recursive, metadata_callback=metadata_callback, progress=True
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
@click.option("--dry-run", is_flag=True, help="Show what would be imported without importing")
@click.option(
    "--delete",
    is_flag=True,
    help="Delete files after successful import (default: move to processed/)",
)
def ingest(dry_run: bool, delete: bool) -> None:
    """
    Auto-import PDFs from the pending inbox folder.

    Scans the pending/ folder and imports any PDFs found. Folder structure
    determines metadata:

    \b
      pending/
        guidance/             -> type=guidance
          FDA/                -> type=guidance, jurisdiction=FDA
          doc.pdf             -> type=guidance, jurisdiction=Other
        standard/ISO/         -> type=standard, jurisdiction=ISO
        doc.pdf               -> type=other, jurisdiction=Other

    After import, files are moved to pending/processed/ (or deleted with --delete).
    """
    pending_dir = config.pending_dir
    processed_dir = pending_dir / "processed"

    if not pending_dir.exists():
        # Create folder structure
        click.echo(f"Creating pending folder structure at {pending_dir}")
        pending_dir.mkdir(parents=True, exist_ok=True)
        for doc_type in config.document_types:
            (pending_dir / doc_type).mkdir(exist_ok=True)
        processed_dir.mkdir(exist_ok=True)
        click.echo(
            "Folder structure created. Drop PDFs into subfolders and run 'regkb ingest' again."
        )
        return

    # Find all PDFs
    pdf_files = list(pending_dir.glob("**/*.pdf"))
    # Exclude processed folder
    pdf_files = [f for f in pdf_files if "processed" not in f.parts]

    if not pdf_files:
        click.echo("No PDFs found in pending folder.")
        return

    click.echo(f"Found {len(pdf_files)} PDF(s) to import")

    imported = 0
    skipped = 0
    errors = []

    for pdf_path in pdf_files:
        # Determine metadata from folder structure
        rel_path = pdf_path.relative_to(pending_dir)
        parts = rel_path.parts[:-1]  # Exclude filename

        doc_type = "other"
        jurisdiction = "Other"

        if len(parts) >= 1:
            # First subfolder = document type
            potential_type = parts[0].lower()
            if potential_type in [t.lower() for t in config.document_types]:
                doc_type = config.normalize_document_type(potential_type)

        if len(parts) >= 2:
            # Second subfolder = jurisdiction
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

                # Content validation warning
                if importer.last_content_warning:
                    click.echo(
                        click.style(
                            f"    !! {importer.last_content_warning}",
                            fg="yellow",
                        )
                    )

                # Report version diff if detected
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

                # Move or delete the file
                if delete:
                    pdf_path.unlink()
                else:
                    processed_dir.mkdir(parents=True, exist_ok=True)
                    dest = processed_dir / pdf_path.name
                    # Handle name conflicts
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


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option("-t", "--type", "doc_type", help="Filter by document type")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction")
@click.option(
    "-n", "--limit", default=10, type=click.IntRange(1, 1000), help="Maximum results (1-1000)"
)
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

    # Warn about invalid filter values (don't block, just warn)
    if doc_type:
        is_valid, error = config.validate_document_type(doc_type)
        if not is_valid:
            click.echo(click.style(f"Warning: {error}", fg="yellow"))
            click.echo("Filter may not match any documents.\n")
    if jurisdiction:
        is_valid, error = config.validate_jurisdiction(jurisdiction)
        if not is_valid:
            click.echo(click.style(f"Warning: {error}", fg="yellow"))
            click.echo("Filter may not match any documents.\n")

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
                excerpt = doc["excerpt"][:200].encode("ascii", "replace").decode("ascii")
                click.echo(f"   Excerpt: {excerpt}")

            click.echo()

    except Exception as e:
        click.echo(click.style(f"Search failed: {e}", fg="red"))
        logger.exception("Search error")


@cli.command()
@click.argument("source")
@click.option("-t", "--title", help="Document title")
@click.option("--type", "doc_type", help="Document type")
@click.option("-j", "--jurisdiction", help="Jurisdiction")
@click.option("-v", "--version", "doc_version", help="Document version")
@click.option("-u", "--url", "source_url", help="Source URL")
@click.option("-d", "--description", help="Description")
def add(
    source: str,
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
    # Check if source is a URL (must check before any Path conversion)
    is_url = source.startswith("http://") or source.startswith("https://")

    # Build metadata with validation
    metadata = {}
    if title:
        metadata["title"] = title
    if doc_type:
        is_valid, error = config.validate_document_type(doc_type)
        if not is_valid:
            click.echo(click.style(error, fg="red"))
            sys.exit(1)
        metadata["document_type"] = config.normalize_document_type(doc_type)
    if jurisdiction:
        is_valid, error = config.validate_jurisdiction(jurisdiction)
        if not is_valid:
            click.echo(click.style(error, fg="red"))
            sys.exit(1)
        metadata["jurisdiction"] = config.normalize_jurisdiction(jurisdiction)
    if doc_version:
        metadata["version"] = doc_version
    if source_url:
        metadata["source_url"] = source_url
    if description:
        metadata["description"] = description

    if is_url:
        click.echo(f"Downloading from {source}...")
        doc_id = importer.import_from_url(source, metadata if metadata else None)
    else:
        source_path = Path(source)
        if not source_path.exists():
            click.echo(click.style(f"File not found: {source}", fg="red"))
            sys.exit(1)
        click.echo(f"Adding {source_path.name}...")
        doc_id = importer.import_file(source_path, metadata if metadata else None)

    if doc_id:
        click.echo(click.style(f"Document added successfully (ID: {doc_id})", fg="green"))

        # Content validation warning
        if importer.last_content_warning:
            click.echo()
            click.echo(
                click.style(
                    f"  Warning: {importer.last_content_warning}",
                    fg="yellow",
                )
            )

        # Report version diff if detected
        vdiff = importer.last_version_diff
        if vdiff:
            click.echo()
            if vdiff.auto_superseded:
                click.echo(click.style("Prior version detected!", fg="cyan", bold=True))
                click.echo(f"  Supersedes: [{vdiff.old_doc_id}] {vdiff.old_doc_title}")
            else:
                click.echo(
                    click.style(
                        "Possible version match — NOT auto-superseded (similarity too low)",
                        fg="yellow",
                        bold=True,
                    )
                )
                click.echo(f"  Candidate: [{vdiff.old_doc_id}] {vdiff.old_doc_title}")
            click.echo(f"  {vdiff.stats.summary()}")
            if vdiff.diff_html_path:
                click.echo(f"  Diff report: {vdiff.diff_html_path}")
            if vdiff.error:
                click.echo(click.style(f"  Note: {vdiff.error}", fg="yellow"))
    else:
        click.echo(click.style("Document already exists or import failed", fg="yellow"))


@cli.command("list")
@click.option("-t", "--type", "doc_type", help="Filter by document type")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction")
@click.option("--all-versions", is_flag=True, help="Include older versions")
@click.option(
    "-n", "--limit", default=20, type=click.IntRange(1, 1000), help="Maximum results (1-1000)"
)
def list_docs(
    doc_type: Optional[str],
    jurisdiction: Optional[str],
    all_versions: bool,
    limit: int,
) -> None:
    """List documents in the knowledge base."""
    # Warn about invalid filter values
    if doc_type:
        is_valid, error = config.validate_document_type(doc_type)
        if not is_valid:
            click.echo(click.style(f"Warning: {error}", fg="yellow"))
    if jurisdiction:
        is_valid, error = config.validate_jurisdiction(jurisdiction)
        if not is_valid:
            click.echo(click.style(f"Warning: {error}", fg="yellow"))

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
    # Validate inputs
    if doc_type:
        is_valid, error = config.validate_document_type(doc_type)
        if not is_valid:
            click.echo(click.style(error, fg="red"))
            sys.exit(1)
    if jurisdiction:
        is_valid, error = config.validate_jurisdiction(jurisdiction)
        if not is_valid:
            click.echo(click.style(error, fg="red"))
            sys.exit(1)

    updates = {}
    if title:
        updates["title"] = title
    if doc_type:
        updates["document_type"] = config.normalize_document_type(doc_type)
    if jurisdiction:
        updates["jurisdiction"] = config.normalize_jurisdiction(jurisdiction)
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
@click.option("--ocr", is_flag=True, help="Force OCR on all pages (requires Tesseract)")
def extract(doc_id: int, ocr: bool) -> None:
    """Re-extract text from a document's PDF."""
    doc = db.get_document(doc_id=doc_id)

    if not doc:
        click.echo(click.style(f"Document not found: {doc_id}", fg="red"))
        sys.exit(1)

    pdf_path = Path(doc["file_path"])
    if not pdf_path.exists():
        click.echo(click.style(f"PDF file not found: {pdf_path}", fg="red"))
        sys.exit(1)

    if ocr:
        from .extraction import _check_ocr_available

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


@cli.command("ocr-reextract")
@click.option("--doc-id", type=int, default=None, help="Re-extract a single document by ID")
@click.option("--all", "all_docs", is_flag=True, help="Re-extract all documents with OCR")
def ocr_reextract(doc_id: int, all_docs: bool) -> None:
    """Batch re-extract documents using OCR.

    Forces OCR on every page. Requires Tesseract to be installed.
    Use --doc-id for a single document or --all for every document in the KB.
    """
    from .extraction import _check_ocr_available

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


@cli.command("diff")
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
    """Compare two documents side-by-side.

    ID1 and ID2 are the document IDs to compare.
    """
    from .diff import compare_documents

    # Look up document titles
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

    # Always show stats
    click.echo(click.style("Document Comparison", fg="cyan", bold=True))
    click.echo(f"  A: [{id1}] {title1}")
    click.echo(f"  B: [{id2}] {title2}")
    click.echo()
    click.echo(result.stats.summary())

    if stats_only:
        return

    # Show colored unified diff
    if result.unified_diff:
        click.echo()
        for line in result.unified_diff.splitlines():
            # Replace characters the console can't encode
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

    # Save HTML report
    if output and result.html_diff:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.html_diff, encoding="utf-8")
        click.echo(click.style(f"\nHTML diff saved to: {output}", fg="green"))


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


@cli.command("download")
@click.option("-j", "--jurisdiction", help="Download only this jurisdiction (EU, UK, US, etc.)")
@click.option(
    "--mandatory-only",
    is_flag=True,
    default=True,
    help="Download only mandatory documents (default)",
)
@click.option(
    "--all", "download_all", is_flag=True, help="Download all documents including optional"
)
@click.option(
    "--import/--no-import", "do_import", default=True, help="Import downloaded files to KB"
)
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

    click.echo(
        click.style(f"\nDownloading {len(docs)} documents...\n", fg="bright_white", bold=True)
    )

    def progress(current, total, message):
        click.echo(f"[{current}/{total}] {message}")

    results = downloader.download_batch(docs, progress_callback=progress, delay=delay)

    # Summary
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(click.style("DOWNLOAD SUMMARY", fg="bright_white", bold=True))
    click.echo(click.style(f"{'=' * 50}", fg="cyan"))
    click.echo(f"  Downloaded: {len(results['success'])}")
    click.echo(f"  Failed:     {len(results['failed'])}")
    click.echo(f"  Skipped:    {len(results['skipped'])} (web pages - manual download)")

    # Show failures
    if results["failed"]:
        click.echo(click.style("\nFailed downloads:", fg="red"))
        for f in results["failed"][:10]:
            click.echo(f"  - {f['title']}: {f['error']}")

    # Show skipped
    if results["skipped"]:
        click.echo(click.style("\nSkipped (manual download required):", fg="yellow"))
        for s in results["skipped"][:10]:
            click.echo(f"  - {s['title']}")
            click.echo(f"    {s['url']}")

    # Import downloaded files
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

    click.echo(f"\n{'=' * 60}")
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
        click.echo(
            click.style(
                f"\n{outdated} document(s) may need updating - check URLs above", fg="yellow"
            )
        )


# ============================================================================
# INTELLIGENCE COMMANDS
# ============================================================================


@cli.group()
def intel() -> None:
    """Regulatory intelligence - monitor and analyze regulatory updates."""
    pass


@intel.command("fetch")
@click.option(
    "-d", "--days", default=7, type=click.IntRange(1, 365), help="Days to look back (1-365)"
)
@click.option("--raw", is_flag=True, help="Show raw entries without filtering")
@click.option("--export", "export_path", type=click.Path(), help="Export to CSV file")
def intel_fetch(days: int, raw: bool, export_path: Optional[str]) -> None:
    """
    Fetch regulatory updates from Index-of-Indexes.

    Fetches the latest regulatory newsletter entries and filters them
    based on configured interests.
    """
    click.echo(click.style("\nRegulatory Intelligence - Fetch", fg="bright_white", bold=True))
    click.echo("=" * 50)

    # Fetch entries
    click.echo(f"\n[1/2] Fetching entries from last {days} days...")
    try:
        fetch_result = newsletter_fetcher.fetch(days=days)
    except Exception as e:
        click.echo(click.style(f"Fetch failed: {e}", fg="red"))
        logger.exception("Newsletter fetch error")
        return

    click.echo(
        f"      Found {fetch_result.total_entries} entries from {fetch_result.sources_fetched} sources"
    )

    if fetch_result.errors:
        click.echo(
            click.style(f"      {len(fetch_result.errors)} errors during fetch", fg="yellow")
        )

    if not fetch_result.entries:
        click.echo(click.style("No entries found.", fg="yellow"))
        return

    # Filter or show raw
    if raw:
        click.echo(
            click.style(
                f"\n[2/2] Showing all {fetch_result.total_entries} entries (unfiltered)", fg="cyan"
            )
        )
        entries_to_show = fetch_result.entries
        filtered_result = None
    else:
        click.echo("\n[2/2] Filtering by interests...")
        filtered_result = content_filter.filter(fetch_result.entries)
        click.echo(f"      Included: {filtered_result.total_included}")
        click.echo(f"      Excluded: {filtered_result.total_excluded}")
        click.echo(f"      High priority: {len(filtered_result.high_priority)}")
        entries_to_show = [fe.entry for fe in filtered_result.included]

    # Export if requested
    if export_path:
        _export_intel_csv(entries_to_show, export_path, filtered_result)
        click.echo(click.style(f"\nExported to: {export_path}", fg="green"))
        return

    # Display results
    click.echo(click.style("\n--- RESULTS ---", fg="bright_white", bold=True))

    if filtered_result:
        # Show high priority first
        if filtered_result.high_priority:
            click.echo(click.style("\nHIGH PRIORITY ALERTS:", fg="red", bold=True))
            for fe in filtered_result.high_priority[:5]:
                _print_intel_entry(fe.entry, fe.alert_level, fe.matched_keywords)

        # Group by category
        by_category = filtered_result.by_category()
        for category, entries in sorted(by_category.items()):
            click.echo(click.style(f"\n{category.upper()}:", fg="cyan", bold=True))
            for fe in entries[:10]:  # Limit per category
                if fe not in filtered_result.high_priority:
                    _print_intel_entry(fe.entry, keywords=fe.matched_keywords)
    else:
        # Show all entries
        for entry in entries_to_show[:30]:
            _print_intel_entry(entry)

    # Summary
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    if filtered_result:
        click.echo(f"Total: {filtered_result.total_included} relevant entries")
        if filtered_result.high_priority:
            click.echo(
                click.style(
                    f"Alert: {len(filtered_result.high_priority)} high-priority items!", fg="red"
                )
            )
    else:
        click.echo(f"Total: {len(entries_to_show)} entries")


def _print_intel_entry(
    entry, alert_level: Optional[str] = None, keywords: Optional[list] = None
) -> None:
    """Print a single intelligence entry."""
    # Alert indicator
    if alert_level == "critical":
        prefix = click.style("[!!!] ", fg="red", bold=True)
    elif alert_level == "high":
        prefix = click.style("[!!]  ", fg="yellow", bold=True)
    else:
        prefix = "      "

    click.echo(f"{prefix}{entry.title}")
    click.echo(f"      {entry.agency} | {entry.date} | {entry.category}")

    if entry.link:
        click.echo(click.style(f"      {entry.link}", fg="blue"))

    if keywords:
        kw_str = ", ".join(keywords[:5])
        click.echo(click.style(f"      Keywords: {kw_str}", fg="green"))


def _export_intel_csv(
    entries, export_path: str, filtered_result: Optional[FilterResult] = None
) -> None:
    """Export intelligence entries to CSV."""
    import csv
    from pathlib import Path

    path = Path(export_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Agency", "Category", "Title", "Link", "Relevance", "Keywords"])

        if filtered_result:
            for fe in filtered_result.included:
                writer.writerow(
                    [
                        fe.entry.date,
                        fe.entry.agency,
                        fe.entry.category,
                        fe.entry.title,
                        fe.entry.link or "",
                        f"{fe.relevance_score:.2f}",
                        "; ".join(fe.matched_keywords),
                    ]
                )
        else:
            for entry in entries:
                writer.writerow(
                    [
                        entry.date,
                        entry.agency,
                        entry.category,
                        entry.title,
                        entry.link or "",
                        "",
                        "",
                    ]
                )


@intel.command("status")
def intel_status() -> None:
    """Show intelligence module status and configuration."""
    click.echo(click.style("\nRegulatory Intelligence Status", fg="bright_white", bold=True))
    click.echo("=" * 50)

    # Filter configuration
    click.echo(click.style("\nFilter Configuration:", fg="cyan"))
    filter_config = content_filter.config

    click.echo("\n  Include categories:")
    for cat in filter_config.get("include_categories", []):
        click.echo(f"    - {cat}")

    click.echo("\n  Exclude categories:")
    for cat in filter_config.get("exclude_categories", []):
        click.echo(f"    - {cat}")

    click.echo(f"\n  Include keywords: {len(filter_config.get('include_keywords', []))} configured")
    click.echo(f"  Exclude keywords: {len(filter_config.get('exclude_keywords', []))} configured")

    # Alert keywords
    alert_kws = filter_config.get("daily_alert_keywords", {})
    click.echo(f"\n  Alert keywords (critical): {len(alert_kws.get('critical', []))}")
    click.echo(f"  Alert keywords (high): {len(alert_kws.get('high', []))}")

    click.echo(click.style("\n  Status: Ready", fg="green"))


@intel.command("sync")
@click.option(
    "-d", "--days", default=7, type=click.IntRange(1, 365), help="Days to look back (1-365)"
)
@click.option("--export", "export_path", type=click.Path(), help="Export report to HTML file")
@click.option("--queue-downloads", is_flag=True, help="Queue downloadable items for approval")
def intel_sync(days: int, export_path: Optional[str], queue_downloads: bool) -> None:
    """
    Sync regulatory updates with knowledge base.

    Fetches updates, filters by interests, checks against KB,
    and generates an intelligence report.
    """
    click.echo(click.style("\nRegulatory Intelligence - Sync", fg="bright_white", bold=True))
    click.echo("=" * 50)

    # Step 1: Fetch
    click.echo(f"\n[1/3] Fetching entries from last {days} days...")
    try:
        fetch_result = newsletter_fetcher.fetch(days=days)
    except Exception as e:
        click.echo(click.style(f"Fetch failed: {e}", fg="red"))
        return

    click.echo(
        f"      Found {fetch_result.total_entries} entries from {fetch_result.sources_fetched} sources"
    )

    if not fetch_result.entries:
        click.echo(click.style("No entries found.", fg="yellow"))
        return

    # Step 2: Filter
    click.echo("\n[2/3] Filtering by interests...")
    filtered_result = content_filter.filter(fetch_result.entries)
    click.echo(f"      Relevant: {filtered_result.total_included}")
    click.echo(f"      Excluded: {filtered_result.total_excluded}")
    click.echo(f"      High priority: {len(filtered_result.high_priority)}")

    if not filtered_result.included:
        click.echo(click.style("No relevant entries found.", fg="yellow"))
        return

    # Step 3: Analyze against KB
    click.echo("\n[3/3] Analyzing against knowledge base...")
    analysis = kb_analyzer.analyze(filtered_result.included)
    click.echo(f"      Already in KB: {analysis.already_in_kb}")
    click.echo(f"      New entries: {analysis.total_analyzed - analysis.already_in_kb}")

    # Queue downloadable items if requested
    if queue_downloads:
        queued = kb_analyzer.queue_for_approval(analysis.results)
        if queued > 0:
            click.echo(
                click.style(f"      Queued {queued} items for download approval", fg="green")
            )

    # Export report if requested
    if export_path:
        _export_intel_report(filtered_result, analysis, export_path, days)
        click.echo(click.style(f"\nReport exported to: {export_path}", fg="green"))

    # Display summary
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(click.style("INTELLIGENCE SUMMARY", fg="bright_white", bold=True))
    click.echo(f"{'=' * 50}")

    # High priority alerts
    if filtered_result.high_priority:
        click.echo(
            click.style(
                f"\n{len(filtered_result.high_priority)} HIGH PRIORITY ITEMS:", fg="red", bold=True
            )
        )
        for fe in filtered_result.high_priority[:5]:
            alert_icon = "[!!!]" if fe.alert_level == "critical" else "[!!]"
            click.echo(f"  {alert_icon} {fe.entry.title[:60]}...")
            click.echo(f"      {fe.entry.agency} | {fe.entry.date}")

    # By category summary
    by_cat = filtered_result.by_category()
    click.echo(click.style("\nBy Category:", fg="cyan"))
    for cat, entries in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        click.echo(f"  {cat}: {len(entries)} updates")

    # By agency summary
    by_agency = filtered_result.by_agency()
    click.echo(click.style("\nTop Agencies:", fg="cyan"))
    for agency, entries in sorted(by_agency.items(), key=lambda x: -len(x[1]))[:5]:
        click.echo(f"  {agency}: {len(entries)} updates")

    click.echo(f"\n{'=' * 50}")
    click.echo(f"Total relevant updates: {filtered_result.total_included}")

    if not export_path:
        click.echo(click.style("\nTip: Use --export report.html to save full report", fg="yellow"))


def _export_intel_report(
    filtered_result: FilterResult, analysis, export_path: str, days: int
) -> None:
    """Export intelligence report to HTML file."""
    from datetime import datetime
    from pathlib import Path

    path = Path(export_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Group by category
    by_category = filtered_result.by_category()

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Regulatory Intelligence Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1a365d; border-bottom: 2px solid #3182ce; padding-bottom: 10px; }}
        h2 {{ color: #2c5282; margin-top: 30px; }}
        .summary {{ background: #ebf8ff; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .alert {{ background: #fed7d7; padding: 10px; border-left: 4px solid #c53030; margin: 10px 0; }}
        .alert.high {{ background: #fefcbf; border-color: #d69e2e; }}
        .entry {{ border: 1px solid #e2e8f0; padding: 15px; margin: 10px 0; border-radius: 8px; }}
        .entry:hover {{ background: #f7fafc; }}
        .meta {{ color: #718096; font-size: 0.9em; }}
        .keywords {{ color: #38a169; font-size: 0.85em; }}
        a {{ color: #3182ce; }}
        .category {{ background: #edf2f7; padding: 5px 10px; border-radius: 4px; display: inline-block; margin: 5px 0; }}
    </style>
</head>
<body>
    <h1>Regulatory Intelligence Report</h1>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | Period: Last {days} days</p>

    <div class="summary">
        <strong>Summary:</strong> {filtered_result.total_included} relevant updates found,
        {len(filtered_result.high_priority)} high priority alerts,
        {analysis.already_in_kb} already in KB
    </div>
"""

    # High priority section
    if filtered_result.high_priority:
        html += "<h2>High Priority Alerts</h2>\n"
        for fe in filtered_result.high_priority:
            alert_class = "alert" if fe.alert_level == "critical" else "alert high"
            html += f"""<div class="{alert_class}">
                <strong>{fe.entry.title}</strong><br>
                <span class="meta">{fe.entry.agency} | {fe.entry.date} | {fe.entry.category}</span><br>
                {f'<a href="{fe.entry.link}" target="_blank">View source</a>' if fe.entry.link else ""}
            </div>\n"""

    # By category
    for category, entries in sorted(by_category.items(), key=lambda x: -len(x[1])):
        html += f'<h2><span class="category">{category}</span> ({len(entries)} updates)</h2>\n'
        for fe in entries[:20]:  # Limit per category
            html += f"""<div class="entry">
                <strong>{fe.entry.title}</strong><br>
                <span class="meta">{fe.entry.agency} | {fe.entry.date}</span><br>
                {f'<span class="keywords">Keywords: {", ".join(fe.matched_keywords[:5])}</span><br>' if fe.matched_keywords else ""}
                {f'<a href="{fe.entry.link}" target="_blank">View source</a>' if fe.entry.link else ""}
            </div>\n"""

    html += """
    <hr>
    <p style="color: #718096; font-size: 0.85em;">
        Generated by RegulatoryKB Intelligence Agent<br>
        Data source: Index-of-Indexes
    </p>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


@intel.command("pending")
@click.option("--all", "show_all", is_flag=True, help="Show all statuses, not just pending")
def intel_pending(show_all: bool) -> None:
    """List documents pending approval for download."""
    click.echo(click.style("\nPending Downloads", fg="bright_white", bold=True))
    click.echo("=" * 50)

    if show_all:
        statuses = ["pending", "approved", "rejected", "downloaded", "failed"]
    else:
        statuses = ["pending"]

    total = 0
    for status in statuses:
        pending = kb_analyzer.get_pending(status)
        if not pending:
            continue

        total += len(pending)
        status_colors = {
            "pending": "yellow",
            "approved": "green",
            "rejected": "red",
            "downloaded": "cyan",
            "failed": "red",
        }
        click.echo(
            click.style(
                f"\n{status.upper()} ({len(pending)}):",
                fg=status_colors.get(status, "white"),
                bold=True,
            )
        )

        for item in pending:
            click.echo(f"\n  [{item.id}] {item.title}")
            click.echo(f"      {item.agency} | {item.date} | Score: {item.relevance_score:.2f}")
            if item.keywords:
                click.echo(
                    click.style(f"      Keywords: {', '.join(item.keywords[:5])}", fg="green")
                )
            click.echo(click.style(f"      {item.url}", fg="blue"))

    if total == 0:
        click.echo(click.style("\nNo pending downloads.", fg="green"))
    else:
        click.echo(f"\n{'=' * 50}")
        stats = kb_analyzer.get_stats()
        click.echo(
            f"Total: {stats.get('pending', 0)} pending, {stats.get('approved', 0)} approved, {stats.get('downloaded', 0)} downloaded"
        )


@intel.command("approve")
@click.argument("ids", nargs=-1, type=int)
@click.option("--all", "approve_all", is_flag=True, help="Approve all pending items")
def intel_approve(ids: tuple, approve_all: bool) -> None:
    """
    Approve pending downloads.

    IDS are the pending download IDs to approve (from 'regkb intel pending').
    """
    if approve_all:
        count = kb_analyzer.approve_all()
        click.echo(click.style(f"Approved all {count} pending downloads", fg="green"))
    elif ids:
        count = kb_analyzer.approve(list(ids))
        click.echo(click.style(f"Approved {count} downloads", fg="green"))
    else:
        click.echo(click.style("Specify IDs or use --all", fg="yellow"))
        return

    # Show next step
    stats = kb_analyzer.get_stats()
    approved = stats.get("approved", 0)
    if approved > 0:
        click.echo(f"\nReady to download {approved} documents.")
        click.echo("Run: regkb intel download")


@intel.command("reject")
@click.argument("ids", nargs=-1, type=int, required=True)
def intel_reject(ids: tuple) -> None:
    """
    Reject pending downloads.

    IDS are the pending download IDs to reject.
    """
    count = kb_analyzer.reject(list(ids))
    click.echo(click.style(f"Rejected {count} downloads", fg="yellow"))


@intel.command("download")
@click.option(
    "--delay",
    default=2.0,
    type=click.FloatRange(0.0, 60.0),
    help="Delay between downloads (0-60 seconds)",
)
def intel_download(delay: float) -> None:
    """Download approved documents and import to KB."""
    import time

    approved = kb_analyzer.get_pending("approved")

    if not approved:
        click.echo(click.style("No approved downloads.", fg="yellow"))
        click.echo("Run: regkb intel sync")
        return

    click.echo(
        click.style(f"\nDownloading {len(approved)} documents", fg="bright_white", bold=True)
    )
    click.echo("=" * 50)

    success_count = 0
    fail_count = 0

    for i, item in enumerate(approved, 1):
        click.echo(f"\n[{i}/{len(approved)}] {item.title[:50]}...")

        try:
            # Download using the existing importer
            doc_id = importer.import_from_url(
                item.url,
                metadata={
                    "title": item.title,
                    "jurisdiction": _infer_jurisdiction(item.agency),
                    "document_type": _infer_doc_type(item.category),
                    "source_url": item.url,
                    "description": f"From Index-of-Indexes: {item.agency} - {item.category}",
                },
            )

            if doc_id:
                kb_analyzer.mark_downloaded(item.id, doc_id)
                click.echo(click.style(f"         Imported (ID: {doc_id})", fg="green"))
                success_count += 1
            else:
                kb_analyzer.mark_failed(item.id, "Import returned None (duplicate or invalid)")
                click.echo(click.style("         Failed: duplicate or invalid file", fg="yellow"))
                fail_count += 1

        except Exception as e:
            kb_analyzer.mark_failed(item.id, str(e))
            click.echo(click.style(f"         Failed: {e}", fg="red"))
            fail_count += 1

        # Delay between downloads
        if i < len(approved) and delay > 0:
            time.sleep(delay)

    # Summary
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(f"Downloaded: {success_count}")
    click.echo(f"Failed: {fail_count}")

    if success_count > 0:
        click.echo(click.style("\nReindexing search...", fg="cyan"))
        search_engine.reindex_all()
        click.echo(click.style("Done!", fg="green"))


def _infer_jurisdiction(agency: str) -> str:
    """Infer jurisdiction from agency name."""
    agency_lower = agency.lower() if agency else ""

    mappings = {
        "fda": "FDA",
        "eu": "EU",
        "european": "EU",
        "mdcg": "EU",
        "ema": "EU",
        "uk": "UK",
        "mhra": "UK",
        "iso": "ISO",
        "iec": "ISO",
        "ich": "ICH",
        "who": "WHO",
        "health canada": "Health Canada",
        "tga": "TGA",
        "pmda": "PMDA",
        "hpra": "Ireland",
    }

    for key, value in mappings.items():
        if key in agency_lower:
            return value

    return "Other"


def _infer_doc_type(category: str) -> str:
    """Infer document type from category."""
    category_lower = category.lower() if category else ""

    if "guidance" in category_lower:
        return "guidance"
    elif "standard" in category_lower:
        return "standard"
    elif "regulation" in category_lower:
        return "regulation"
    elif "legislation" in category_lower or "law" in category_lower:
        return "legislation"
    elif "policy" in category_lower:
        return "policy"
    elif "report" in category_lower:
        return "report"
    else:
        return "guidance"  # Default for regulatory updates


@intel.command("summary")
@click.option(
    "-d", "--days", default=7, type=click.IntRange(1, 365), help="Days to look back (1-365)"
)
@click.option(
    "-n", "--limit", default=10, type=click.IntRange(1, 50), help="Max entries to summarize (1-50)"
)
@click.option(
    "--style",
    type=click.Choice(["layperson", "technical", "brief"]),
    default="layperson",
    help="Summary style",
)
@click.option("--high-priority-only", is_flag=True, help="Only summarize high-priority items")
@click.option("--export", "export_path", type=click.Path(), help="Export summaries to HTML file")
@click.option("--no-cache", is_flag=True, help="Bypass summary cache")
def intel_summary(
    days: int,
    limit: int,
    style: str,
    high_priority_only: bool,
    export_path: Optional[str],
    no_cache: bool,
) -> None:
    """
    Generate LLM-powered summaries of regulatory updates.

    Uses Claude to create layperson-friendly explanations of recent
    regulatory changes, their impact, and required actions.

    Requires ANTHROPIC_API_KEY environment variable to be set.
    """
    click.echo(
        click.style("\nRegulatory Intelligence - Summary Generation", fg="bright_white", bold=True)
    )
    click.echo("=" * 50)

    # Check for API key
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        click.echo(
            click.style("\nError: ANTHROPIC_API_KEY environment variable not set.", fg="red")
        )
        click.echo("Set it with: set ANTHROPIC_API_KEY=your-api-key")
        click.echo("\nYou can get an API key from: https://console.anthropic.com/")
        return

    # Step 1: Fetch
    click.echo(f"\n[1/3] Fetching entries from last {days} days...")
    try:
        fetch_result = newsletter_fetcher.fetch(days=days)
    except Exception as e:
        click.echo(click.style(f"Fetch failed: {e}", fg="red"))
        return

    click.echo(f"      Found {fetch_result.total_entries} entries")

    if not fetch_result.entries:
        click.echo(click.style("No entries found.", fg="yellow"))
        return

    # Step 2: Filter
    click.echo("\n[2/3] Filtering by interests...")
    filtered_result = content_filter.filter(fetch_result.entries)

    if high_priority_only:
        entries_to_summarize = filtered_result.high_priority[:limit]
        click.echo(f"      High priority items: {len(entries_to_summarize)}")
    else:
        entries_to_summarize = filtered_result.included[:limit]
        click.echo(f"      Relevant items: {len(entries_to_summarize)} (limited to {limit})")

    if not entries_to_summarize:
        click.echo(click.style("No entries to summarize.", fg="yellow"))
        return

    # Step 3: Generate summaries
    click.echo(f"\n[3/3] Generating {style} summaries...")
    click.echo(f"      Model: {intel_summarizer.model}")

    summaries = []
    with tqdm(total=len(entries_to_summarize), desc="Summarizing") as pbar:
        for entry in entries_to_summarize:
            summary = intel_summarizer.summarize(entry, style=style, use_cache=not no_cache)
            summaries.append((entry, summary))
            pbar.update(1)

    # Export if requested
    if export_path:
        _export_summary_report(summaries, export_path, style, days)
        click.echo(click.style(f"\nReport exported to: {export_path}", fg="green"))
        return

    # Display summaries
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(click.style("REGULATORY UPDATE SUMMARIES", fg="bright_white", bold=True))
    click.echo(f"{'=' * 50}")

    for i, (entry, summary) in enumerate(summaries, 1):
        click.echo(click.style(f"\n[{i}] {entry.entry.title[:70]}", fg="bright_white", bold=True))
        click.echo(f"    {entry.entry.agency} | {entry.entry.date}")

        if summary.what_happened:
            click.echo(click.style("\n    What happened:", fg="cyan"))
            click.echo(f"    {summary.what_happened}")

        if summary.why_it_matters:
            click.echo(click.style("\n    Why it matters:", fg="yellow"))
            click.echo(f"    {summary.why_it_matters}")

        if summary.action_needed:
            click.echo(click.style("\n    Action needed:", fg="green"))
            click.echo(f"    {summary.action_needed}")

        if entry.entry.link:
            click.echo(click.style(f"\n    Source: {entry.entry.link}", fg="blue"))

        click.echo(f"\n    {'─' * 46}")

    # Cache stats
    stats = intel_summarizer.get_cache_stats()
    click.echo(f"\n{'=' * 50}")
    click.echo(f"Summaries generated: {len(summaries)}")
    click.echo(f"Cache: {stats['total']} total cached summaries")


def _export_summary_report(summaries, export_path: str, style: str, days: int) -> None:
    """Export summaries to HTML file."""
    from datetime import datetime
    from pathlib import Path

    path = Path(export_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Regulatory Intelligence Summaries</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f7fafc; }}
        h1 {{ color: #1a365d; border-bottom: 2px solid #3182ce; padding-bottom: 10px; }}
        .summary-card {{ background: white; border: 1px solid #e2e8f0; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .summary-card h2 {{ color: #2d3748; margin-top: 0; font-size: 1.1em; }}
        .meta {{ color: #718096; font-size: 0.9em; margin-bottom: 15px; }}
        .section {{ margin: 15px 0; }}
        .section-title {{ color: #2c5282; font-weight: 600; font-size: 0.9em; text-transform: uppercase; margin-bottom: 5px; }}
        .what {{ border-left: 3px solid #3182ce; padding-left: 10px; }}
        .why {{ border-left: 3px solid #d69e2e; padding-left: 10px; }}
        .action {{ border-left: 3px solid #38a169; padding-left: 10px; }}
        a {{ color: #3182ce; }}
        .footer {{ color: #718096; font-size: 0.85em; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <h1>Regulatory Intelligence Summaries</h1>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | Period: Last {days} days | Style: {style}</p>
    <p><strong>{len(summaries)} updates summarized</strong></p>
"""

    for entry, summary in summaries:
        html += f"""
    <div class="summary-card">
        <h2>{entry.entry.title}</h2>
        <div class="meta">{entry.entry.agency} | {entry.entry.date} | {entry.entry.category}</div>

        <div class="section what">
            <div class="section-title">What Happened</div>
            <p>{summary.what_happened or "Summary not available"}</p>
        </div>

        <div class="section why">
            <div class="section-title">Why It Matters</div>
            <p>{summary.why_it_matters or "See original source"}</p>
        </div>

        <div class="section action">
            <div class="section-title">Action Needed</div>
            <p>{summary.action_needed or "Information only"}</p>
        </div>

        {f'<p><a href="{entry.entry.link}" target="_blank">View original source →</a></p>' if entry.entry.link else ""}
    </div>
"""

    html += """
    <div class="footer">
        <p>Generated by RegulatoryKB Intelligence Agent<br>
        Summaries powered by Claude (Anthropic)<br>
        Data source: Index-of-Indexes</p>
    </div>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


@intel.command("cache")
@click.option("--clear", is_flag=True, help="Clear all cached summaries")
@click.option("--stats", "show_stats", is_flag=True, help="Show cache statistics")
def intel_cache(clear: bool, show_stats: bool) -> None:
    """Manage the summary cache."""
    if clear:
        count = intel_summarizer.clear_cache()
        click.echo(click.style(f"Cleared {count} cached summaries", fg="green"))
    elif show_stats:
        stats = intel_summarizer.get_cache_stats()
        click.echo(click.style("\nSummary Cache Statistics", fg="bright_white", bold=True))
        click.echo("=" * 30)
        click.echo(f"Total cached: {stats['total']}")
        if stats["by_style"]:
            click.echo("\nBy style:")
            for style, count in stats["by_style"].items():
                click.echo(f"  {style}: {count}")
    else:
        stats = intel_summarizer.get_cache_stats()
        click.echo(f"Cache contains {stats['total']} summaries")
        click.echo("Use --stats for details or --clear to reset")


@intel.command("email")
@click.option(
    "-d", "--days", default=7, type=click.IntRange(1, 365), help="Days to look back (1-365)"
)
@click.option(
    "--type",
    "email_type",
    type=click.Choice(["weekly", "daily", "test"]),
    default="weekly",
    help="Email type",
)
@click.option(
    "--to", "recipients", multiple=True, help="Override recipients (can specify multiple)"
)
@click.option("--dry-run", is_flag=True, help="Generate email but don't send (saves to file)")
@click.option(
    "-n", "--limit", default=20, type=click.IntRange(1, 50), help="Max entries to include"
)
def intel_email(days: int, email_type: str, recipients: tuple, dry_run: bool, limit: int) -> None:
    """
    Send regulatory intelligence email digest.

    Sends weekly digest, daily alerts, or test email via SMTP.

    Requires SMTP_USERNAME and SMTP_PASSWORD environment variables.
    """
    from datetime import datetime, timedelta

    click.echo(
        click.style(
            f"\nRegulatory Intelligence - {email_type.title()} Email", fg="bright_white", bold=True
        )
    )
    click.echo("=" * 50)

    # Handle test email separately
    if email_type == "test":
        if not recipients:
            click.echo(click.style("Error: --to recipient required for test email", fg="red"))
            return

        click.echo(f"\nSending test email to: {recipients[0]}")
        result = intel_emailer.send_test_email(recipients[0])

        if result.success:
            click.echo(click.style("Test email sent successfully!", fg="green"))
        else:
            click.echo(click.style(f"Failed: {result.error}", fg="red"))
        return

    # Check for SMTP credentials
    import os

    if not dry_run and (not os.environ.get("SMTP_USERNAME") or not os.environ.get("SMTP_PASSWORD")):
        click.echo(click.style("\nError: SMTP credentials not set.", fg="red"))
        click.echo("Set environment variables:")
        click.echo("  set SMTP_USERNAME=your-email@gmail.com")
        click.echo("  set SMTP_PASSWORD=your-app-password")
        click.echo(
            "\nFor Gmail, use an App Password: https://support.google.com/accounts/answer/185833"
        )
        click.echo("\nOr use --dry-run to generate email without sending.")
        return

    # Step 1: Fetch
    click.echo(f"\n[1/4] Fetching entries from last {days} days...")
    try:
        fetch_result = newsletter_fetcher.fetch(days=days)
    except Exception as e:
        click.echo(click.style(f"Fetch failed: {e}", fg="red"))
        return

    click.echo(f"      Found {fetch_result.total_entries} entries")

    if not fetch_result.entries:
        click.echo(click.style("No entries found.", fg="yellow"))
        return

    # Step 2: Filter
    click.echo("\n[2/4] Filtering by interests...")
    filtered_result = content_filter.filter(fetch_result.entries)
    click.echo(f"      Relevant: {filtered_result.total_included}")
    click.echo(f"      High priority: {len(filtered_result.high_priority)}")

    if not filtered_result.included:
        click.echo(click.style("No relevant entries to email.", fg="yellow"))
        return

    # For daily alerts, only send if there are high-priority items
    if email_type == "daily" and not filtered_result.high_priority:
        click.echo(click.style("No high-priority items for daily alert.", fg="yellow"))
        return

    # Step 3: Generate summaries (optional but recommended)
    click.echo("\n[3/4] Generating summaries...")

    entries_to_process = (
        filtered_result.high_priority if email_type == "daily" else filtered_result.included[:limit]
    )
    entries_with_summaries = []

    # Check if we have API key for summaries
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    if has_api_key:
        with tqdm(total=len(entries_to_process), desc="Summarizing") as pbar:
            for entry in entries_to_process:
                try:
                    summary = intel_summarizer.summarize(entry, style="layperson", use_cache=True)
                    entries_with_summaries.append((entry, summary))
                except Exception:
                    entries_with_summaries.append((entry, None))
                pbar.update(1)
    else:
        click.echo("      (Skipping summaries - ANTHROPIC_API_KEY not set)")
        entries_with_summaries = [(entry, None) for entry in entries_to_process]

    # Step 4: Send email
    click.echo("\n[4/4] Preparing email...")

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

    # Prepare high priority entries
    high_priority_with_summaries = [
        (e, s) for e, s in entries_with_summaries if e in filtered_result.high_priority
    ]

    # Override recipients if specified
    recipient_list = list(recipients) if recipients else None

    if dry_run:
        # Save to file instead of sending
        output_file = f"intel_email_{email_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        if email_type == "weekly":
            # Generate HTML manually for preview
            from .intelligence.emailer import WEEKLY_TEMPLATE

            alerts_section = intel_emailer._generate_alerts_section(high_priority_with_summaries)
            summaries_section = intel_emailer._generate_summaries_section(entries_with_summaries)

            categories = {e.entry.category for e, _ in entries_with_summaries if e.entry.category}

            html = WEEKLY_TEMPLATE.format(
                date_range=date_range,
                total_updates=len(entries_with_summaries),
                high_priority=len(high_priority_with_summaries),
                categories=len(categories),
                alerts_section=alerts_section,
                summaries_section=summaries_section,
            )
        else:
            from .intelligence.emailer import DAILY_ALERT_TEMPLATE

            alerts_content = ""
            for entry, summary in high_priority_with_summaries:
                alerts_content += f"""
                <div class="alert">
                    <h2>{entry.entry.title}</h2>
                    <div class="meta">{entry.entry.agency} | {entry.entry.category}</div>
                    <div class="content">
                        {f"<p><strong>What:</strong> {summary.what_happened}</p>" if summary and summary.what_happened else ""}
                    </div>
                </div>
                """
            html = DAILY_ALERT_TEMPLATE.format(
                date=datetime.now().strftime("%B %d, %Y"),
                alerts_content=alerts_content,
            )

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        click.echo(click.style(f"\nDry run - email saved to: {output_file}", fg="green"))
        click.echo("Open this file in a browser to preview the email.")
        return

    # Actually send the email
    if email_type == "weekly":
        result = intel_emailer.send_weekly_digest(
            entries_with_summaries=entries_with_summaries,
            high_priority=high_priority_with_summaries,
            date_range=date_range,
            recipients=recipient_list,
        )
    else:  # daily
        result = intel_emailer.send_daily_alert(
            alerts=high_priority_with_summaries,
            recipients=recipient_list,
        )

    # Report result
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    if result.success:
        click.echo(click.style("Email sent successfully!", fg="green"))
        click.echo(f"Recipients: {result.recipients_sent}")
    else:
        click.echo(click.style(f"Email failed: {result.error}", fg="red"))


@intel.command("run")
@click.option("-d", "--days", default=7, type=click.IntRange(1, 365), help="Days to look back")
@click.option("--email/--no-email", default=False, help="Send email after processing")
@click.option("--export", "export_path", type=click.Path(), help="Export report to file")
def intel_run(days: int, email: bool, export_path: Optional[str]) -> None:
    """
    Run the full intelligence workflow.

    Fetches updates, filters, analyzes, generates summaries, and optionally
    sends email - all in one command.
    """
    from datetime import datetime, timedelta

    click.echo(click.style("\nRegulatory Intelligence Agent", fg="bright_white", bold=True))
    click.echo("=" * 50)

    # Step 1: Fetch
    click.echo(f"\n[1/5] Fetching entries from last {days} days...")
    try:
        fetch_result = newsletter_fetcher.fetch(days=days)
    except Exception as e:
        click.echo(click.style(f"Fetch failed: {e}", fg="red"))
        return

    click.echo(
        f"      Found {fetch_result.total_entries} entries from {fetch_result.sources_fetched} sources"
    )

    if not fetch_result.entries:
        click.echo(click.style("No entries found.", fg="yellow"))
        return

    # Step 2: Filter
    click.echo("\n[2/5] Filtering by interests...")
    filtered_result = content_filter.filter(fetch_result.entries)
    click.echo(f"      Relevant: {filtered_result.total_included}")
    click.echo(f"      Excluded: {filtered_result.total_excluded}")
    click.echo(f"      High priority: {len(filtered_result.high_priority)}")

    if not filtered_result.included:
        click.echo(click.style("No relevant entries found.", fg="yellow"))
        return

    # Step 3: Analyze against KB
    click.echo("\n[3/5] Analyzing against knowledge base...")
    analysis = kb_analyzer.analyze(filtered_result.included)
    click.echo(f"      Already in KB: {analysis.already_in_kb}")
    click.echo(f"      New entries: {analysis.total_analyzed - analysis.already_in_kb}")

    # Step 4: Generate summaries (if API key available)
    click.echo("\n[4/5] Generating summaries...")
    import os

    entries_with_summaries = []

    if os.environ.get("ANTHROPIC_API_KEY"):
        entries_to_summarize = filtered_result.included[:20]  # Top 20
        with tqdm(total=len(entries_to_summarize), desc="Summarizing") as pbar:
            for entry in entries_to_summarize:
                try:
                    summary = intel_summarizer.summarize(entry, use_cache=True)
                    entries_with_summaries.append((entry, summary))
                except Exception:
                    entries_with_summaries.append((entry, None))
                pbar.update(1)
    else:
        click.echo("      (Skipping - ANTHROPIC_API_KEY not set)")
        entries_with_summaries = [(e, None) for e in filtered_result.included[:20]]

    # Step 5: Export/Email
    click.echo("\n[5/5] Finalizing...")

    if export_path:
        _export_summary_report(entries_with_summaries, export_path, "layperson", days)
        click.echo(click.style(f"      Report exported to: {export_path}", fg="green"))

    if email:
        if not os.environ.get("SMTP_USERNAME") or not os.environ.get("SMTP_PASSWORD"):
            click.echo(click.style("      Email skipped - SMTP credentials not set", fg="yellow"))
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

            high_priority_with_summaries = [
                (e, s) for e, s in entries_with_summaries if e in filtered_result.high_priority
            ]

            result = intel_emailer.send_weekly_digest(
                entries_with_summaries=entries_with_summaries,
                high_priority=high_priority_with_summaries,
                date_range=date_range,
            )

            if result.success:
                click.echo(
                    click.style(
                        f"      Email sent to {result.recipients_sent} recipients", fg="green"
                    )
                )
            else:
                click.echo(click.style(f"      Email failed: {result.error}", fg="red"))

    # Summary
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(click.style("COMPLETE", fg="green", bold=True))
    click.echo(f"  Processed: {filtered_result.total_included} relevant updates")
    click.echo(f"  Alerts: {len(filtered_result.high_priority)} high-priority items")
    click.echo(f"  Summaries: {len([s for _, s in entries_with_summaries if s])} generated")


@intel.command("setup")
@click.option(
    "--type",
    "-t",
    "setup_type",
    type=click.Choice(["batch", "taskxml", "imap", "all"]),
    default="batch",
    help="Type of setup files to generate",
)
@click.option(
    "--schedule",
    "-s",
    type=click.Choice(["weekly", "daily", "monthly"]),
    default="weekly",
    help="Schedule type for Task Scheduler XML",
)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output directory for generated files"
)
def intel_setup(setup_type: str, schedule: str, output: Optional[Path]) -> None:
    """
    Generate automation setup files.

    Creates batch scripts and/or Windows Task Scheduler XML for automated runs.

    Examples:

      regkb intel setup                    # Generate batch scripts

      regkb intel setup -t taskxml         # Generate Task Scheduler XML

      regkb intel setup -t imap            # Generate IMAP poll script

      regkb intel setup -t all -o scripts  # Generate all to scripts/
    """
    output_dir = output or config.base_dir

    files_created = []

    if setup_type in ("batch", "all"):
        # Generate batch scripts
        for script_type in ["weekly", "daily", "monthly"]:
            script_content = generate_batch_script(
                script_type=script_type,
                include_email=True,
                export_report=True,
            )
            script_path = output_dir / f"run_intel_{script_type}.bat"
            with open(script_path, "w") as f:
                f.write(script_content)
            files_created.append(script_path)

    if setup_type in ("imap", "all"):
        # Generate IMAP poll script
        imap_content = generate_imap_batch_script(
            poll_interval_minutes=config.get("intelligence.reply_processing.poll_interval", 30),
            send_confirmations=True,
        )
        imap_path = output_dir / "run_intel_imap.bat"
        with open(imap_path, "w") as f:
            f.write(imap_content)
        files_created.append(imap_path)

    if setup_type in ("taskxml", "all"):
        # Generate Task Scheduler XML
        xml_content = generate_windows_task_xml(
            task_name=f"RegulatoryKB_Intel_{schedule.title()}",
            schedule=schedule,
        )
        xml_path = output_dir / f"task_intel_{schedule}.xml"
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml_content)
        files_created.append(xml_path)

    click.echo(click.style("Setup files generated:", fg="green"))
    for path in files_created:
        click.echo(f"  - {path}")

    click.echo()
    click.echo("Next steps:")
    if setup_type in ("batch", "all"):
        click.echo("  1. Edit batch files to set your API keys and email credentials")
        click.echo("  2. Test manually: run_intel_weekly.bat")
    if setup_type in ("imap", "all"):
        click.echo("  3. Set IMAP_USERNAME and IMAP_PASSWORD in environment")
        click.echo("  4. Run run_intel_imap.bat to start polling for digest replies")
    if setup_type in ("taskxml", "all"):
        click.echo("  5. Import Task Scheduler XML:")
        click.echo(
            f'     schtasks /create /xml "{output_dir / f"task_intel_{schedule}.xml"}" /tn "RegulatoryKB_Intel"'
        )


@intel.command("schedule-status")
def intel_schedule_status() -> None:
    """
    Show scheduler state and next run times.

    Displays when each scheduled task last ran and when it should run next.
    """
    click.echo(click.style("Scheduler State", fg="cyan", bold=True))
    click.echo("=" * 40)

    # Last runs
    click.echo("\nLast Runs:")

    if scheduler_state.last_weekly_run:
        click.echo(f"  Weekly:  {scheduler_state.last_weekly_run.strftime('%Y-%m-%d %H:%M')}")
    else:
        click.echo("  Weekly:  Never")

    if scheduler_state.last_daily_run:
        click.echo(f"  Daily:   {scheduler_state.last_daily_run.strftime('%Y-%m-%d %H:%M')}")
    else:
        click.echo("  Daily:   Never")

    if scheduler_state.last_monthly_run:
        click.echo(f"  Monthly: {scheduler_state.last_monthly_run.strftime('%Y-%m-%d %H:%M')}")
    else:
        click.echo("  Monthly: Never")

    # Should run checks
    click.echo("\nShould Run Now:")
    click.echo(f"  Weekly:  {'Yes' if scheduler_state.should_run_weekly() else 'No'}")
    click.echo(f"  Daily:   {'Yes' if scheduler_state.should_run_daily() else 'No'}")
    click.echo(f"  Monthly: {'Yes' if scheduler_state.should_run_monthly() else 'No'}")

    # Config info
    click.echo("\nSchedule Config:")
    weekly_day = config.get("intelligence.schedule.weekly_day", "monday")
    weekly_time = config.get("intelligence.schedule.weekly_time", "08:00")
    monthly_day = config.get("intelligence.schedule.monthly_day", 1)
    daily_time = config.get("intelligence.schedule.daily_alert_time", "09:00")

    click.echo(f"  Weekly:  {weekly_day.title()} at {weekly_time}")
    click.echo(f"  Daily:   {daily_time}")
    click.echo(f"  Monthly: Day {monthly_day} of month")


@intel.command("poll")
@click.option("--once", is_flag=True, help="Poll once and exit (don't loop)")
@click.option("--no-confirm", is_flag=True, help="Don't send confirmation emails")
def intel_poll(once: bool, no_confirm: bool) -> None:
    """
    Poll IMAP for digest reply emails and process download requests.

    Checks for replies to weekly digest emails containing download requests
    (e.g., "Download: 07, 12") and processes them.

    Requires IMAP_USERNAME and IMAP_PASSWORD (or SMTP_* equivalents).
    """
    import os

    click.echo(click.style("\nRegulatory Intelligence - IMAP Poll", fg="bright_white", bold=True))
    click.echo("=" * 50)

    # Check for credentials
    username = os.environ.get("IMAP_USERNAME") or os.environ.get("SMTP_USERNAME")
    password = os.environ.get("IMAP_PASSWORD") or os.environ.get("SMTP_PASSWORD")

    if not username or not password:
        click.echo(click.style("\nError: IMAP credentials not configured.", fg="red"))
        click.echo("Set environment variables:")
        click.echo("  set IMAP_USERNAME=your-email@gmail.com")
        click.echo("  set IMAP_PASSWORD=your-app-password")
        click.echo("\n(Or use SMTP_USERNAME/SMTP_PASSWORD - same credentials work for Gmail)")
        return

    click.echo("\nPolling for replies...")

    result = reply_handler.process_all_pending(mark_read=True)

    if result.requests_processed == 0:
        click.echo(click.style("No download requests found.", fg="yellow"))
        return

    # Summary
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(click.style("PROCESSING COMPLETE", fg="bright_white", bold=True))
    click.echo(f"{'=' * 50}")

    if result.successful:
        click.echo(click.style(f"\nSUCCESSFUL ({len(result.successful)}):", fg="green", bold=True))
        for download in result.successful:
            seq = download.entry.entry_id.split("-")[-1]
            kb_id = f" -> KB ID: {download.kb_doc_id}" if download.kb_doc_id else ""
            click.echo(f"  [{seq}] {download.entry.title[:50]}...{kb_id}")

    if result.needs_manual:
        click.echo(
            click.style(f"\nNEEDS MANUAL URL ({len(result.needs_manual)}):", fg="yellow", bold=True)
        )
        for download in result.needs_manual:
            seq = download.entry.entry_id.split("-")[-1]
            click.echo(f"  [{seq}] {download.entry.title[:50]}...")
            click.echo(f"       Original: {download.entry.link}")

    if result.failed:
        click.echo(click.style(f"\nFAILED ({len(result.failed)}):", fg="red", bold=True))
        for download in result.failed:
            seq = download.entry.entry_id.split("-")[-1]
            click.echo(f"  [{seq}] {download.entry.title[:50]}...")
            click.echo(f"       Error: {download.error}")

    # Send confirmation email if we have results and email is enabled
    if not no_confirm and (result.successful or result.needs_manual or result.failed):
        # Get requester email from the first request
        requests = reply_handler.poll_for_replies(mark_read=False)
        if requests:
            requester = requests[0].requester_email
            click.echo(f"\nSending confirmation email to {requester}...")

            email_result = intel_emailer.send_download_confirmation(
                successful=result.successful,
                needs_manual=result.needs_manual,
                failed=result.failed,
                requester_email=requester,
            )

            if email_result.success:
                click.echo(click.style("Confirmation email sent.", fg="green"))
            else:
                click.echo(
                    click.style(f"Failed to send confirmation: {email_result.error}", fg="red")
                )

    click.echo(f"\n{'=' * 50}")
    click.echo(
        f"Total: {len(result.successful)} successful, {len(result.failed)} failed, {len(result.needs_manual)} need manual URL"
    )


@intel.command("resolve-url")
@click.argument("url")
def intel_resolve_url(url: str) -> None:
    """
    Test URL resolution for a given URL.

    Checks if a URL can be resolved to a downloadable document.
    Useful for testing LinkedIn and other social media URLs.
    """
    click.echo(click.style("\nURL Resolution Test", fg="bright_white", bold=True))
    click.echo("=" * 50)
    click.echo(f"\nOriginal URL: {url}")

    result = url_resolver.resolve(url)

    click.echo("\nResolution Result:")
    click.echo(
        f"  Success:       {click.style('Yes', fg='green') if result.success else click.style('No', fg='red')}"
    )
    click.echo(f"  Resolved URL:  {result.resolved_url or 'N/A'}")
    click.echo(f"  Domain:        {result.domain or 'N/A'}")
    click.echo(f"  Document Type: {result.document_type or 'unknown'}")
    click.echo(f"  Is Paid:       {'Yes' if result.is_paid else 'No'}")
    click.echo(f"  Needs Manual:  {'Yes' if result.needs_manual else 'No'}")

    if result.error:
        click.echo(click.style(f"  Error:         {result.error}", fg="red"))

    if result.all_links_found:
        click.echo(f"\nLinks found on page ({len(result.all_links_found)}):")
        for link in result.all_links_found[:10]:
            click.echo(f"  - {link[:80]}")


@intel.command("download-entry")
@click.argument("ids", nargs=-1, required=True)
@click.option("--url", help="Override URL for download (for manual URL resolution)")
def intel_download_entry(ids: tuple, url: Optional[str]) -> None:
    """
    Manually trigger download for specific entry IDs.

    IDS are entry IDs from digest emails (e.g., "07 12" or "2026-0125-07").

    Use --url to provide a direct URL when automatic resolution failed.
    """
    click.echo(click.style("\nManual Entry Download", fg="bright_white", bold=True))
    click.echo("=" * 50)

    # Look up entries
    entries = digest_tracker.lookup_entries(list(ids))

    if not entries:
        click.echo(click.style(f"No entries found for IDs: {', '.join(ids)}", fg="red"))
        return

    click.echo(f"\nFound {len(entries)} entries:")
    for entry in entries:
        click.echo(f"  [{entry.entry_id}] {entry.title[:60]}...")
        click.echo(f"            Status: {entry.download_status}")

    # If URL override provided, use it for all entries
    if url:
        click.echo(f"\nUsing override URL: {url}")

    # Process downloads
    success_count = 0
    fail_count = 0

    for entry in entries:
        click.echo(f"\n[{entry.entry_id}] Processing...")

        # Use override URL or entry's URL
        download_url = url or entry.link

        if not download_url:
            click.echo(click.style("  No URL available", fg="red"))
            fail_count += 1
            continue

        # Resolve URL if it's a social media link
        resolve_result = url_resolver.resolve(download_url)

        if resolve_result.needs_manual and not url:
            click.echo(click.style("  URL needs manual resolution", fg="yellow"))
            click.echo("  Use --url to provide direct document URL")
            digest_tracker.update_entry_status(entry.entry_id, "manual_needed")
            fail_count += 1
            continue

        if resolve_result.is_paid:
            click.echo(click.style(f"  Paid domain: {resolve_result.domain}", fg="yellow"))
            fail_count += 1
            continue

        final_url = resolve_result.resolved_url or download_url

        try:
            doc_id = importer.import_from_url(
                final_url,
                metadata={
                    "title": entry.title,
                    "source_url": final_url,
                    "description": f"Downloaded from digest entry {entry.entry_id}",
                },
            )

            if doc_id:
                digest_tracker.update_entry_status(
                    entry.entry_id,
                    "downloaded",
                    kb_doc_id=doc_id,
                    resolved_url=final_url,
                )
                click.echo(click.style(f"  Downloaded -> KB ID: {doc_id}", fg="green"))
                success_count += 1
            else:
                click.echo(click.style("  Import failed (duplicate or invalid)", fg="yellow"))
                fail_count += 1

        except Exception as e:
            click.echo(click.style(f"  Error: {e}", fg="red"))
            digest_tracker.update_entry_status(
                entry.entry_id,
                "failed",
                error_message=str(e),
            )
            fail_count += 1

    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(f"Downloaded: {success_count}, Failed: {fail_count}")

    if success_count > 0:
        click.echo("\nReindexing search...")
        search_engine.reindex_all()
        click.echo(click.style("Done!", fg="green"))


@intel.command("digest-entries")
@click.option("--date", help="Filter by digest date (YYYY-MM-DD)")
@click.option("-n", "--limit", default=30, help="Maximum entries to show")
def intel_digest_entries(date: Optional[str], limit: int) -> None:
    """
    List tracked digest entries.

    Shows entries that have been sent in digest emails and their download status.
    """
    click.echo(click.style("\nTracked Digest Entries", fg="bright_white", bold=True))
    click.echo("=" * 50)

    entries = digest_tracker.get_recent_entries(digest_date=date, limit=limit)

    if not entries:
        click.echo(click.style("No entries found.", fg="yellow"))
        return

    # Group by status
    by_status = {}
    for entry in entries:
        status = entry.download_status
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(entry)

    status_colors = {
        "pending": "yellow",
        "downloaded": "green",
        "failed": "red",
        "manual_needed": "yellow",
    }

    for status, status_entries in sorted(by_status.items()):
        color = status_colors.get(status, "white")
        click.echo(click.style(f"\n{status.upper()} ({len(status_entries)}):", fg=color, bold=True))

        for entry in status_entries[:15]:
            seq = entry.entry_id.split("-")[-1]
            kb_info = f" -> KB:{entry.kb_doc_id}" if entry.kb_doc_id else ""
            click.echo(f"  [{seq}] {entry.title[:55]}...{kb_info}")

    # Stats
    stats = digest_tracker.get_stats()
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(f"Total digests: {stats['total_digests']}")
    click.echo(f"Total entries tracked: {stats['total_entries']}")
    if stats["last_digest_date"]:
        click.echo(f"Last digest: {stats['last_digest_date']}")


@cli.command()
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


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
