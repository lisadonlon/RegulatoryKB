"""Core top-level CLI commands (search/metadata/stats)."""

import logging
import sys
from typing import Optional

import click

from regkb.config import config
from regkb.services import get_db, get_importer, get_search_engine

logger = logging.getLogger(__name__)


def register_core_commands(cli: click.Group) -> None:
    """Register core top-level commands on the main CLI group."""
    cli.add_command(search)
    cli.add_command(add)
    cli.add_command(list_docs)
    cli.add_command(show)
    cli.add_command(update)
    cli.add_command(stats)


@click.command()
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
    """Search for documents using natural language."""
    query_str = " ".join(query)
    click.echo(f"Searching for: {query_str}")

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
        results = get_search_engine().search(
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
                excerpt = doc["excerpt"][:200].encode("ascii", "replace").decode("ascii")
                click.echo(f"   Excerpt: {excerpt}")

            click.echo()

    except Exception as e:
        click.echo(click.style(f"Search failed: {e}", fg="red"))
        logger.exception("Search error")


@click.command()
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
    """Add a single document to the knowledge base."""
    importer = get_importer()
    is_url = source.startswith("http://") or source.startswith("https://")

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
        from pathlib import Path

        source_path = Path(source)
        if not source_path.exists():
            click.echo(click.style(f"File not found: {source}", fg="red"))
            sys.exit(1)
        click.echo(f"Adding {source_path.name}...")
        doc_id = importer.import_file(source_path, metadata if metadata else None)

    if doc_id:
        click.echo(click.style(f"Document added successfully (ID: {doc_id})", fg="green"))

        if importer.last_content_warning:
            click.echo()
            click.echo(click.style(f"  Warning: {importer.last_content_warning}", fg="yellow"))

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


@click.command("list")
@click.option("-t", "--type", "doc_type", help="Filter by document type")
@click.option("-j", "--jurisdiction", help="Filter by jurisdiction")
@click.option("--all-versions", is_flag=True, help="Include older versions")
@click.option(
    "-n", "--limit", default=20, type=click.IntRange(1, 1000), help="Maximum results (1-1000)"
)
def list_docs(doc_type: Optional[str], jurisdiction: Optional[str], all_versions: bool, limit: int) -> None:
    """List documents in the knowledge base."""
    db = get_db()

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


@click.command()
@click.argument("doc_id", type=int)
def show(doc_id: int) -> None:
    """Show detailed information about a document."""
    db = get_db()
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


@click.command()
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
    db = get_db()

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


@click.command()
def stats() -> None:
    """Show knowledge base statistics."""
    stats_data = get_db().get_statistics()

    click.echo(click.style("\nRegulatory Knowledge Base Statistics", fg="bright_white", bold=True))
    click.echo("=" * 40)
    click.echo(f"Total documents:    {stats_data['total_documents']}")
    click.echo(f"Latest versions:    {stats_data['latest_versions']}")
    click.echo(f"Total imports:      {stats_data['total_imports']}")

    if stats_data.get("by_type"):
        click.echo("\nBy Document Type:")
        for doc_type, count in sorted(stats_data["by_type"].items()):
            click.echo(f"  {doc_type}: {count}")

    if stats_data.get("by_jurisdiction"):
        click.echo("\nBy Jurisdiction:")
        for jur, count in sorted(stats_data["by_jurisdiction"].items()):
            click.echo(f"  {jur}: {count}")
