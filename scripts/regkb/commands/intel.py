"""Intel command group for the RegKB CLI."""

import logging
from pathlib import Path
from typing import Optional

import click
from tqdm import tqdm

from regkb.config import config
from regkb.intelligence.analyzer import analyzer as kb_analyzer
from regkb.intelligence.digest_tracker import digest_tracker
from regkb.intelligence.emailer import emailer as intel_emailer
from regkb.intelligence.fetcher import fetcher as newsletter_fetcher
from regkb.intelligence.filter import FilterResult, content_filter
from regkb.intelligence.reply_handler import reply_handler
from regkb.intelligence.scheduler import (
    generate_batch_script,
    generate_imap_batch_script,
    generate_windows_task_xml,
    scheduler_state,
)
from regkb.intelligence.summarizer import summarizer as intel_summarizer
from regkb.intelligence.url_resolver import url_resolver
from regkb.services import get_importer, get_search_engine

logger = logging.getLogger(__name__)


def _get_search_engine():
    return get_search_engine()


def _get_importer():
    return get_importer()


@click.group(name="intel")
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
    click.echo(click.style("\nRegulatory Intelligence - Fetch", fg="bright_white", bold=True))
    click.echo("=" * 50)
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
        click.echo(click.style(f"      {len(fetch_result.errors)} errors during fetch", fg="yellow"))
    if not fetch_result.entries:
        click.echo(click.style("No entries found.", fg="yellow"))
        return

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

    if export_path:
        _export_intel_csv(entries_to_show, export_path, filtered_result)
        click.echo(click.style(f"\nExported to: {export_path}", fg="green"))
        return

    click.echo(click.style("\n--- RESULTS ---", fg="bright_white", bold=True))
    if filtered_result:
        if filtered_result.high_priority:
            click.echo(click.style("\nHIGH PRIORITY ALERTS:", fg="red", bold=True))
            for fe in filtered_result.high_priority[:5]:
                _print_intel_entry(fe.entry, fe.alert_level, fe.matched_keywords)

        by_category = filtered_result.by_category()
        for category, entries in sorted(by_category.items()):
            click.echo(click.style(f"\n{category.upper()}:", fg="cyan", bold=True))
            for fe in entries[:10]:
                if fe not in filtered_result.high_priority:
                    _print_intel_entry(fe.entry, keywords=fe.matched_keywords)
    else:
        for entry in entries_to_show[:30]:
            _print_intel_entry(entry)

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


def _print_intel_entry(entry, alert_level: Optional[str] = None, keywords: Optional[list] = None) -> None:
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


def _export_intel_csv(entries, export_path: str, filtered_result: Optional[FilterResult] = None) -> None:
    import csv

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
                writer.writerow([entry.date, entry.agency, entry.category, entry.title, entry.link or "", "", ""])


@intel.command("status")
def intel_status() -> None:
    click.echo(click.style("\nRegulatory Intelligence Status", fg="bright_white", bold=True))
    click.echo("=" * 50)

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

    alert_kws = filter_config.get("daily_alert_keywords", {})
    click.echo(f"\n  Alert keywords (critical): {len(alert_kws.get('critical', []))}")
    click.echo(f"  Alert keywords (high): {len(alert_kws.get('high', []))}")
    click.echo(click.style("\n  Status: Ready", fg="green"))


@intel.command("sync")
@click.option("-d", "--days", default=7, type=click.IntRange(1, 365), help="Days to look back (1-365)")
@click.option("--export", "export_path", type=click.Path(), help="Export report to HTML file")
@click.option("--queue-downloads", is_flag=True, help="Queue downloadable items for approval")
def intel_sync(days: int, export_path: Optional[str], queue_downloads: bool) -> None:
    click.echo(click.style("\nRegulatory Intelligence - Sync", fg="bright_white", bold=True))
    click.echo("=" * 50)
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

    click.echo("\n[2/3] Filtering by interests...")
    filtered_result = content_filter.filter(fetch_result.entries)
    click.echo(f"      Relevant: {filtered_result.total_included}")
    click.echo(f"      Excluded: {filtered_result.total_excluded}")
    click.echo(f"      High priority: {len(filtered_result.high_priority)}")
    if not filtered_result.included:
        click.echo(click.style("No relevant entries found.", fg="yellow"))
        return

    click.echo("\n[3/3] Analyzing against knowledge base...")
    analysis = kb_analyzer.analyze(filtered_result.included)
    click.echo(f"      Already in KB: {analysis.already_in_kb}")
    click.echo(f"      New entries: {analysis.total_analyzed - analysis.already_in_kb}")

    if queue_downloads:
        queued = kb_analyzer.queue_for_approval(analysis.results)
        if queued > 0:
            click.echo(click.style(f"      Queued {queued} items for download approval", fg="green"))

    if export_path:
        _export_intel_report(filtered_result, analysis, export_path, days)
        click.echo(click.style(f"\nReport exported to: {export_path}", fg="green"))

    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(click.style("INTELLIGENCE SUMMARY", fg="bright_white", bold=True))
    click.echo(f"{'=' * 50}")

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

    by_cat = filtered_result.by_category()
    click.echo(click.style("\nBy Category:", fg="cyan"))
    for cat, entries in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        click.echo(f"  {cat}: {len(entries)} updates")

    by_agency = filtered_result.by_agency()
    click.echo(click.style("\nTop Agencies:", fg="cyan"))
    for agency, entries in sorted(by_agency.items(), key=lambda x: -len(x[1]))[:5]:
        click.echo(f"  {agency}: {len(entries)} updates")

    click.echo(f"\n{'=' * 50}")
    click.echo(f"Total relevant updates: {filtered_result.total_included}")
    if not export_path:
        click.echo(click.style("\nTip: Use --export report.html to save full report", fg="yellow"))


def _export_intel_report(filtered_result: FilterResult, analysis, export_path: str, days: int) -> None:
    from datetime import datetime

    path = Path(export_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    by_category = filtered_result.by_category()

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset=\"utf-8\">
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
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Period: Last {days} days</p>

    <div class=\"summary\">
        <strong>Summary:</strong> {filtered_result.total_included} relevant updates found,
        {len(filtered_result.high_priority)} high priority alerts,
        {analysis.already_in_kb} already in KB
    </div>
"""

    if filtered_result.high_priority:
        html += "<h2>High Priority Alerts</h2>\n"
        for fe in filtered_result.high_priority:
            alert_class = "alert" if fe.alert_level == "critical" else "alert high"
            html += f"""<div class=\"{alert_class}\">
                <strong>{fe.entry.title}</strong><br>
                <span class=\"meta\">{fe.entry.agency} | {fe.entry.date} | {fe.entry.category}</span><br>
                {f'<a href="{fe.entry.link}" target="_blank">View source</a>' if fe.entry.link else ''}
            </div>\n"""

    for category, entries in sorted(by_category.items(), key=lambda x: -len(x[1])):
        html += f'<h2><span class=\"category\">{category}</span> ({len(entries)} updates)</h2>\n'
        for fe in entries[:20]:
            html += f"""<div class=\"entry\">
                <strong>{fe.entry.title}</strong><br>
                <span class=\"meta\">{fe.entry.agency} | {fe.entry.date}</span><br>
                {f'<span class=\"keywords\">Keywords: {", ".join(fe.matched_keywords[:5])}</span><br>' if fe.matched_keywords else ''}
                {f'<a href="{fe.entry.link}" target="_blank">View source</a>' if fe.entry.link else ''}
            </div>\n"""

    html += """
    <hr>
    <p style=\"color: #718096; font-size: 0.85em;\">
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
    click.echo(click.style("\nPending Downloads", fg="bright_white", bold=True))
    click.echo("=" * 50)

    statuses = ["pending", "approved", "rejected", "downloaded", "failed"] if show_all else ["pending"]
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
        click.echo(click.style(f"\n{status.upper()} ({len(pending)}):", fg=status_colors.get(status, "white"), bold=True))

        for item in pending:
            click.echo(f"\n  [{item.id}] {item.title}")
            click.echo(f"      {item.agency} | {item.date} | Score: {item.relevance_score:.2f}")
            if item.keywords:
                click.echo(click.style(f"      Keywords: {', '.join(item.keywords[:5])}", fg="green"))
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
    if approve_all:
        count = kb_analyzer.approve_all()
        click.echo(click.style(f"Approved all {count} pending downloads", fg="green"))
    elif ids:
        count = kb_analyzer.approve(list(ids))
        click.echo(click.style(f"Approved {count} downloads", fg="green"))
    else:
        click.echo(click.style("Specify IDs or use --all", fg="yellow"))
        return

    stats = kb_analyzer.get_stats()
    approved = stats.get("approved", 0)
    if approved > 0:
        click.echo(f"\nReady to download {approved} documents.")
        click.echo("Run: regkb intel download")


@intel.command("reject")
@click.argument("ids", nargs=-1, type=int, required=True)
def intel_reject(ids: tuple) -> None:
    count = kb_analyzer.reject(list(ids))
    click.echo(click.style(f"Rejected {count} downloads", fg="yellow"))


@intel.command("download")
@click.option("--delay", default=2.0, type=click.FloatRange(0.0, 60.0), help="Delay between downloads (0-60 seconds)")
def intel_download(delay: float) -> None:
    import time

    approved = kb_analyzer.get_pending("approved")
    if not approved:
        click.echo(click.style("No approved downloads.", fg="yellow"))
        click.echo("Run: regkb intel sync")
        return

    click.echo(click.style(f"\nDownloading {len(approved)} documents", fg="bright_white", bold=True))
    click.echo("=" * 50)
    success_count = 0
    fail_count = 0

    for i, item in enumerate(approved, 1):
        click.echo(f"\n[{i}/{len(approved)}] {item.title[:50]}...")
        try:
            doc_id = _get_importer().import_from_url(
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

        if i < len(approved) and delay > 0:
            time.sleep(delay)

    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(f"Downloaded: {success_count}")
    click.echo(f"Failed: {fail_count}")
    if success_count > 0:
        click.echo(click.style("\nReindexing search...", fg="cyan"))
        _get_search_engine().reindex_all()
        click.echo(click.style("Done!", fg="green"))


def _infer_jurisdiction(agency: str) -> str:
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
        return "guidance"


@intel.command("summary")
@click.option("-d", "--days", default=7, type=click.IntRange(1, 365), help="Days to look back (1-365)")
@click.option("-n", "--limit", default=10, type=click.IntRange(1, 50), help="Max entries to summarize (1-50)")
@click.option("--style", type=click.Choice(["layperson", "technical", "brief"]), default="layperson", help="Summary style")
@click.option("--high-priority-only", is_flag=True, help="Only summarize high-priority items")
@click.option("--export", "export_path", type=click.Path(), help="Export summaries to HTML file")
@click.option("--no-cache", is_flag=True, help="Bypass summary cache")
def intel_summary(days: int, limit: int, style: str, high_priority_only: bool, export_path: Optional[str], no_cache: bool) -> None:
    click.echo(click.style("\nRegulatory Intelligence - Summary Generation", fg="bright_white", bold=True))
    click.echo("=" * 50)
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        click.echo(click.style("\nError: ANTHROPIC_API_KEY environment variable not set.", fg="red"))
        click.echo("Set it with: set ANTHROPIC_API_KEY=your-api-key")
        click.echo("\nYou can get an API key from: https://console.anthropic.com/")
        return

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

    click.echo(f"\n[3/3] Generating {style} summaries...")
    click.echo(f"      Model: {intel_summarizer.model}")
    summaries = []
    with tqdm(total=len(entries_to_summarize), desc="Summarizing") as pbar:
        for entry in entries_to_summarize:
            summary = intel_summarizer.summarize(entry, style=style, use_cache=not no_cache)
            summaries.append((entry, summary))
            pbar.update(1)

    if export_path:
        _export_summary_report(summaries, export_path, style, days)
        click.echo(click.style(f"\nReport exported to: {export_path}", fg="green"))
        return

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

    stats = intel_summarizer.get_cache_stats()
    click.echo(f"\n{'=' * 50}")
    click.echo(f"Summaries generated: {len(summaries)}")
    click.echo(f"Cache: {stats['total']} total cached summaries")


def _export_summary_report(summaries, export_path: str, style: str, days: int) -> None:
    from datetime import datetime

    path = Path(export_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset=\"utf-8\">
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
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Period: Last {days} days | Style: {style}</p>
    <p><strong>{len(summaries)} updates summarized</strong></p>
"""

    for entry, summary in summaries:
        html += f"""
    <div class=\"summary-card\">
        <h2>{entry.entry.title}</h2>
        <div class=\"meta\">{entry.entry.agency} | {entry.entry.date} | {entry.entry.category}</div>

        <div class=\"section what\">
            <div class=\"section-title\">What Happened</div>
            <p>{summary.what_happened or 'Summary not available'}</p>
        </div>

        <div class=\"section why\">
            <div class=\"section-title\">Why It Matters</div>
            <p>{summary.why_it_matters or 'See original source'}</p>
        </div>

        <div class=\"section action\">
            <div class=\"section-title\">Action Needed</div>
            <p>{summary.action_needed or 'Information only'}</p>
        </div>

        {f'<p><a href="{entry.entry.link}" target="_blank">View original source →</a></p>' if entry.entry.link else ''}
    </div>
"""

    html += """
    <div class=\"footer\">
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
@click.option("-d", "--days", default=7, type=click.IntRange(1, 365), help="Days to look back (1-365)")
@click.option("--type", "email_type", type=click.Choice(["weekly", "daily", "test"]), default="weekly", help="Email type")
@click.option("--to", "recipients", multiple=True, help="Override recipients (can specify multiple)")
@click.option("--dry-run", is_flag=True, help="Generate email but don't send (saves to file)")
@click.option("-n", "--limit", default=20, type=click.IntRange(1, 50), help="Max entries to include")
def intel_email(days: int, email_type: str, recipients: tuple, dry_run: bool, limit: int) -> None:
    from datetime import datetime, timedelta
    import os

    click.echo(click.style(f"\nRegulatory Intelligence - {email_type.title()} Email", fg="bright_white", bold=True))
    click.echo("=" * 50)

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

    if not dry_run and (not os.environ.get("SMTP_USERNAME") or not os.environ.get("SMTP_PASSWORD")):
        click.echo(click.style("\nError: SMTP credentials not set.", fg="red"))
        click.echo("Set environment variables:")
        click.echo("  set SMTP_USERNAME=your-email@gmail.com")
        click.echo("  set SMTP_PASSWORD=your-app-password")
        click.echo("\nFor Gmail, use an App Password: https://support.google.com/accounts/answer/185833")
        click.echo("\nOr use --dry-run to generate email without sending.")
        return

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

    click.echo("\n[2/4] Filtering by interests...")
    filtered_result = content_filter.filter(fetch_result.entries)
    click.echo(f"      Relevant: {filtered_result.total_included}")
    click.echo(f"      High priority: {len(filtered_result.high_priority)}")
    if not filtered_result.included:
        click.echo(click.style("No relevant entries to email.", fg="yellow"))
        return
    if email_type == "daily" and not filtered_result.high_priority:
        click.echo(click.style("No high-priority items for daily alert.", fg="yellow"))
        return

    click.echo("\n[3/4] Generating summaries...")
    entries_to_process = filtered_result.high_priority if email_type == "daily" else filtered_result.included[:limit]
    entries_with_summaries = []
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

    click.echo("\n[4/4] Preparing email...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    high_priority_with_summaries = [(e, s) for e, s in entries_with_summaries if e in filtered_result.high_priority]
    recipient_list = list(recipients) if recipients else None

    if dry_run:
        output_file = f"intel_email_{email_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        if email_type == "weekly":
            from regkb.intelligence.emailer import WEEKLY_TEMPLATE

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
            from regkb.intelligence.emailer import DAILY_ALERT_TEMPLATE

            alerts_content = ""
            for entry, summary in high_priority_with_summaries:
                alerts_content += f"""
                <div class=\"alert\">
                    <h2>{entry.entry.title}</h2>
                    <div class=\"meta\">{entry.entry.agency} | {entry.entry.category}</div>
                    <div class=\"content\">
                        {f"<p><strong>What:</strong> {summary.what_happened}</p>" if summary and summary.what_happened else ""}
                    </div>
                </div>
                """
            html = DAILY_ALERT_TEMPLATE.format(date=datetime.now().strftime("%B %d, %Y"), alerts_content=alerts_content)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        click.echo(click.style(f"\nDry run - email saved to: {output_file}", fg="green"))
        click.echo("Open this file in a browser to preview the email.")
        return

    if email_type == "weekly":
        result = intel_emailer.send_weekly_digest(
            entries_with_summaries=entries_with_summaries,
            high_priority=high_priority_with_summaries,
            date_range=date_range,
            recipients=recipient_list,
        )
    else:
        result = intel_emailer.send_daily_alert(alerts=high_priority_with_summaries, recipients=recipient_list)

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
    from datetime import datetime, timedelta
    import os

    click.echo(click.style("\nRegulatory Intelligence Agent", fg="bright_white", bold=True))
    click.echo("=" * 50)
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

    click.echo("\n[2/5] Filtering by interests...")
    filtered_result = content_filter.filter(fetch_result.entries)
    click.echo(f"      Relevant: {filtered_result.total_included}")
    click.echo(f"      Excluded: {filtered_result.total_excluded}")
    click.echo(f"      High priority: {len(filtered_result.high_priority)}")
    if not filtered_result.included:
        click.echo(click.style("No relevant entries found.", fg="yellow"))
        return

    click.echo("\n[3/5] Analyzing against knowledge base...")
    analysis = kb_analyzer.analyze(filtered_result.included)
    click.echo(f"      Already in KB: {analysis.already_in_kb}")
    click.echo(f"      New entries: {analysis.total_analyzed - analysis.already_in_kb}")

    click.echo("\n[4/5] Generating summaries...")
    entries_with_summaries = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        entries_to_summarize = filtered_result.included[:20]
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
            high_priority_with_summaries = [(e, s) for e, s in entries_with_summaries if e in filtered_result.high_priority]
            result = intel_emailer.send_weekly_digest(
                entries_with_summaries=entries_with_summaries,
                high_priority=high_priority_with_summaries,
                date_range=date_range,
            )
            if result.success:
                click.echo(click.style(f"      Email sent to {result.recipients_sent} recipients", fg="green"))
            else:
                click.echo(click.style(f"      Email failed: {result.error}", fg="red"))

    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(click.style("COMPLETE", fg="green", bold=True))
    click.echo(f"  Processed: {filtered_result.total_included} relevant updates")
    click.echo(f"  Alerts: {len(filtered_result.high_priority)} high-priority items")
    click.echo(f"  Summaries: {len([s for _, s in entries_with_summaries if s])} generated")


@intel.command("setup")
@click.option("--type", "-t", "setup_type", type=click.Choice(["batch", "taskxml", "imap", "all"]), default="batch", help="Type of setup files to generate")
@click.option("--schedule", "-s", type=click.Choice(["weekly", "daily", "monthly"]), default="weekly", help="Schedule type for Task Scheduler XML")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output directory for generated files")
def intel_setup(setup_type: str, schedule: str, output: Optional[Path]) -> None:
    output_dir = output or config.base_dir
    files_created = []

    if setup_type in ("batch", "all"):
        for script_type in ["weekly", "daily", "monthly"]:
            script_content = generate_batch_script(script_type=script_type, include_email=True, export_report=True)
            script_path = output_dir / f"run_intel_{script_type}.bat"
            with open(script_path, "w") as f:
                f.write(script_content)
            files_created.append(script_path)

    if setup_type in ("imap", "all"):
        imap_content = generate_imap_batch_script(
            poll_interval_minutes=config.get("intelligence.reply_processing.poll_interval", 30),
            send_confirmations=True,
        )
        imap_path = output_dir / "run_intel_imap.bat"
        with open(imap_path, "w") as f:
            f.write(imap_content)
        files_created.append(imap_path)

    if setup_type in ("taskxml", "all"):
        xml_content = generate_windows_task_xml(task_name=f"RegulatoryKB_Intel_{schedule.title()}", schedule=schedule)
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
        click.echo(f'     schtasks /create /xml "{output_dir / f"task_intel_{schedule}.xml"}" /tn "RegulatoryKB_Intel"')


@intel.command("schedule-status")
def intel_schedule_status() -> None:
    click.echo(click.style("Scheduler State", fg="cyan", bold=True))
    click.echo("=" * 40)
    click.echo("\nLast Runs:")
    click.echo(f"  Weekly:  {scheduler_state.last_weekly_run.strftime('%Y-%m-%d %H:%M') if scheduler_state.last_weekly_run else 'Never'}")
    click.echo(f"  Daily:   {scheduler_state.last_daily_run.strftime('%Y-%m-%d %H:%M') if scheduler_state.last_daily_run else 'Never'}")
    click.echo(f"  Monthly: {scheduler_state.last_monthly_run.strftime('%Y-%m-%d %H:%M') if scheduler_state.last_monthly_run else 'Never'}")

    click.echo("\nShould Run Now:")
    click.echo(f"  Weekly:  {'Yes' if scheduler_state.should_run_weekly() else 'No'}")
    click.echo(f"  Daily:   {'Yes' if scheduler_state.should_run_daily() else 'No'}")
    click.echo(f"  Monthly: {'Yes' if scheduler_state.should_run_monthly() else 'No'}")

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
    import os

    click.echo(click.style("\nRegulatory Intelligence - IMAP Poll", fg="bright_white", bold=True))
    click.echo("=" * 50)

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
        click.echo(click.style(f"\nNEEDS MANUAL URL ({len(result.needs_manual)}):", fg="yellow", bold=True))
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

    if not no_confirm and (result.successful or result.needs_manual or result.failed):
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
                click.echo(click.style(f"Failed to send confirmation: {email_result.error}", fg="red"))

    click.echo(f"\n{'=' * 50}")
    click.echo(
        f"Total: {len(result.successful)} successful, {len(result.failed)} failed, {len(result.needs_manual)} need manual URL"
    )


@intel.command("resolve-url")
@click.argument("url")
def intel_resolve_url(url: str) -> None:
    click.echo(click.style("\nURL Resolution Test", fg="bright_white", bold=True))
    click.echo("=" * 50)
    click.echo(f"\nOriginal URL: {url}")

    result = url_resolver.resolve(url)
    click.echo("\nResolution Result:")
    click.echo(f"  Success:       {click.style('Yes', fg='green') if result.success else click.style('No', fg='red')}")
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
    click.echo(click.style("\nManual Entry Download", fg="bright_white", bold=True))
    click.echo("=" * 50)

    entries = digest_tracker.lookup_entries(list(ids))
    if not entries:
        click.echo(click.style(f"No entries found for IDs: {', '.join(ids)}", fg="red"))
        return

    click.echo(f"\nFound {len(entries)} entries:")
    for entry in entries:
        click.echo(f"  [{entry.entry_id}] {entry.title[:60]}...")
        click.echo(f"            Status: {entry.download_status}")

    if url:
        click.echo(f"\nUsing override URL: {url}")

    success_count = 0
    fail_count = 0
    for entry in entries:
        click.echo(f"\n[{entry.entry_id}] Processing...")
        download_url = url or entry.link
        if not download_url:
            click.echo(click.style("  No URL available", fg="red"))
            fail_count += 1
            continue

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
            doc_id = _get_importer().import_from_url(
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
            digest_tracker.update_entry_status(entry.entry_id, "failed", error_message=str(e))
            fail_count += 1

    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(f"Downloaded: {success_count}, Failed: {fail_count}")
    if success_count > 0:
        click.echo("\nReindexing search...")
        _get_search_engine().reindex_all()
        click.echo(click.style("Done!", fg="green"))


@intel.command("digest-entries")
@click.option("--date", help="Filter by digest date (YYYY-MM-DD)")
@click.option("-n", "--limit", default=30, help="Maximum entries to show")
def intel_digest_entries(date: Optional[str], limit: int) -> None:
    click.echo(click.style("\nTracked Digest Entries", fg="bright_white", bold=True))
    click.echo("=" * 50)

    entries = digest_tracker.get_recent_entries(digest_date=date, limit=limit)
    if not entries:
        click.echo(click.style("No entries found.", fg="yellow"))
        return

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

    stats = digest_tracker.get_stats()
    click.echo(click.style(f"\n{'=' * 50}", fg="cyan"))
    click.echo(f"Total digests: {stats['total_digests']}")
    click.echo(f"Total entries tracked: {stats['total_entries']}")
    if stats["last_digest_date"]:
        click.echo(f"Last digest: {stats['last_digest_date']}")
