"""
Telegram message formatting utilities.

Telegram MarkdownV2 requires escaping special characters:
  _ * [ ] ( ) ~ ` > # + - = | { } . !
"""

import re


def escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text))


def bold(text: str) -> str:
    """Wrap text in bold MarkdownV2."""
    return f"*{escape_md(text)}*"


def italic(text: str) -> str:
    """Wrap text in italic MarkdownV2."""
    return f"_{escape_md(text)}_"


def code(text: str) -> str:
    """Wrap text in inline code MarkdownV2."""
    return f"`{escape_md(text)}`"


def link(text: str, url: str) -> str:
    """Create a MarkdownV2 link."""
    return f"[{escape_md(text)}]({_escape_url(url)})"


def _escape_url(url: str) -> str:
    """Escape parentheses in URLs for MarkdownV2."""
    return url.replace("(", "%28").replace(")", "%29")


def format_entry(entry, index: int = 0) -> str:
    """Format a single filtered entry for Telegram display."""
    parts = []
    parts.append(f"{bold(f'#{index + 1}')} {bold(entry.entry.title[:80])}")

    meta = []
    if entry.entry.agency:
        meta.append(escape_md(entry.entry.agency))
    if entry.entry.category:
        meta.append(escape_md(entry.entry.category))
    if entry.entry.date:
        meta.append(escape_md(entry.entry.date))
    if meta:
        parts.append(italic(" · ".join(meta)))

    if entry.alert_level:
        level_emoji = {"CRITICAL": "🔴", "HIGH": "🟠"}.get(entry.alert_level, "🔵")
        parts.append(f"{level_emoji} {escape_md(entry.alert_level)}")

    if entry.matched_keywords:
        tags = ", ".join(entry.matched_keywords[:5])
        parts.append(f"Tags: {escape_md(tags)}")

    if entry.entry.link:
        parts.append(link("View source", entry.entry.link))

    return "\n".join(parts)


def format_digest(entries: list, title: str = "Regulatory Digest") -> str:
    """Format a full digest for Telegram."""
    parts = [f"📋 {bold(title)}", ""]

    if not entries:
        parts.append(escape_md("No relevant entries found."))
        return "\n".join(parts)

    # Group by alert level
    critical = [e for e in entries if e.alert_level == "CRITICAL"]
    high = [e for e in entries if e.alert_level == "HIGH"]
    normal = [e for e in entries if e.alert_level not in ("CRITICAL", "HIGH")]

    idx = 0
    if critical:
        parts.append(f"🔴 {bold('CRITICAL')}")
        for entry in critical:
            parts.append(format_entry(entry, idx))
            parts.append("")
            idx += 1

    if high:
        parts.append(f"🟠 {bold('HIGH PRIORITY')}")
        for entry in high:
            parts.append(format_entry(entry, idx))
            parts.append("")
            idx += 1

    if normal:
        parts.append(f"📄 {bold('Updates')}")
        for entry in normal[:10]:
            parts.append(format_entry(entry, idx))
            parts.append("")
            idx += 1
        if len(normal) > 10:
            parts.append(escape_md(f"... and {len(normal) - 10} more"))

    parts.append(escape_md(f"Total: {len(entries)} entries"))
    return "\n".join(parts)


def format_stats(db_stats: dict, pending_count: int = 0) -> str:
    """Format KB statistics for Telegram."""
    parts = [f"📊 {bold('Knowledge Base Status')}", ""]

    total = db_stats.get("total_documents", 0)
    parts.append(f"Documents: {escape_md(str(total))}")

    by_type = db_stats.get("by_type", {})
    if by_type:
        type_items = [f"{escape_md(k)}: {escape_md(str(v))}" for k, v in by_type.items()]
        parts.append(f"By type: {', '.join(type_items)}")

    by_jurisdiction = db_stats.get("by_jurisdiction", {})
    if by_jurisdiction:
        jur_items = [f"{escape_md(k)}: {escape_md(str(v))}" for k, v in by_jurisdiction.items()]
        parts.append(f"By jurisdiction: {', '.join(jur_items)}")

    if pending_count > 0:
        parts.append(f"\n⏳ Pending downloads: {escape_md(str(pending_count))}")

    return "\n".join(parts)


def format_pending_item(item, index: int = 0) -> str:
    """Format a single pending download item."""
    parts = []
    title = (
        getattr(item, "title", str(item)) if not isinstance(item, dict) else item.get("title", "")
    )
    parts.append(f"{bold(f'#{index + 1}')} {escape_md(title[:60])}")

    agency = getattr(item, "agency", None) if not isinstance(item, dict) else item.get("agency")
    if agency:
        parts.append(italic(agency))

    score = (
        getattr(item, "relevance_score", None)
        if not isinstance(item, dict)
        else item.get("relevance_score")
    )
    if score:
        parts.append(f"Score: {escape_md(f'{score:.2f}')}")

    return "\n".join(parts)


def format_search_result(result: dict, index: int = 0) -> str:
    """Format a single search result for Telegram."""
    parts = []
    title = result.get("title", "Untitled")
    parts.append(f"{bold(f'#{index + 1}')} {escape_md(title[:80])}")

    meta = []
    if result.get("jurisdiction"):
        meta.append(result["jurisdiction"])
    if result.get("document_type"):
        meta.append(result["document_type"])
    if meta:
        parts.append(italic(" · ".join(meta)))

    score = result.get("score") or result.get("similarity")
    if score:
        parts.append(f"Relevance: {escape_md(f'{score:.0%}')}")

    excerpt = result.get("excerpt", "")
    if excerpt:
        parts.append(escape_md(excerpt[:150]))

    return "\n".join(parts)


def format_search_results(results: list[dict], query: str) -> str:
    """Format search results for Telegram."""
    parts = [f"🔍 {bold('Search')}: {escape_md(query)}", ""]

    if not results:
        parts.append(escape_md("No results found."))
        return "\n".join(parts)

    for i, result in enumerate(results):
        parts.append(format_search_result(result, i))
        parts.append("")

    parts.append(escape_md(f"{len(results)} result(s)"))
    return "\n".join(parts)
