"""
Enhanced search handler with jurisdiction filters, pagination, and follow-up.

Parses natural language queries to extract jurisdiction hints and keywords,
then routes to SearchEngine with appropriate filters.
"""

import asyncio
import logging
import re
from typing import Optional

from regkb.telegram.auth import require_auth
from regkb.telegram.formatters import (
    bold,
    escape_md,
    format_search_result,
)

logger = logging.getLogger(__name__)

# Maximum Telegram message length
MAX_MESSAGE_LENGTH = 4096

# Jurisdiction aliases for natural language parsing
JURISDICTION_ALIASES: dict[str, str] = {
    "fda": "FDA",
    "us": "FDA",
    "american": "FDA",
    "united states": "FDA",
    "eu": "EU",
    "european": "EU",
    "europe": "EU",
    "mdr": "EU",
    "ivdr": "EU",
    "uk": "UK",
    "british": "UK",
    "mhra": "UK",
    "iso": "ISO",
    "iec": "ISO",
    "ich": "ICH",
    "ireland": "Ireland",
    "irish": "Ireland",
    "hpra": "Ireland",
    "canada": "Health Canada",
    "canadian": "Health Canada",
    "tga": "TGA",
    "australia": "TGA",
    "australian": "TGA",
    "japan": "PMDA",
    "japanese": "PMDA",
    "pmda": "PMDA",
    "ema": "EMA",
    "who": "WHO",
}

# Document type aliases
DOC_TYPE_ALIASES: dict[str, str] = {
    "guidance": "guidance",
    "guide": "guidance",
    "guideline": "guidance",
    "standard": "standard",
    "regulation": "regulation",
    "rule": "regulation",
    "law": "legislation",
    "legislation": "legislation",
    "policy": "policy",
    "procedure": "procedure",
    "report": "report",
    "advisory": "advisory",
}

# Per-user search context for "tell me more" follow-up
_search_context: dict[int, dict] = {}


def parse_query(raw_query: str) -> dict:
    """Parse a natural language query to extract filters and search terms.

    Examples:
        "FDA cybersecurity guidance" -> jurisdiction=FDA, doc_type=guidance, query="cybersecurity"
        "What EU MDR documents do we have?" -> jurisdiction=EU, query="MDR"
        "ISO 13485" -> jurisdiction=ISO, query="13485"

    Returns:
        Dict with keys: query, jurisdiction, document_type
    """
    jurisdiction = None
    document_type = None
    query_words = []

    # Strip question phrasing
    raw_clean = re.sub(
        r"^(what|which|show me|find|list|do we have|are there)\s+",
        "",
        raw_query.lower().strip(),
    )
    raw_clean = re.sub(
        r"\s*(documents?|docs?|files?)\s+(do we have|are there)\s*\??$", "", raw_clean
    )
    raw_clean = re.sub(r"\?$", "", raw_clean).strip()

    for word in raw_clean.split():
        # Check jurisdiction aliases
        if word in JURISDICTION_ALIASES and jurisdiction is None:
            jurisdiction = JURISDICTION_ALIASES[word]
            continue

        # Check two-word jurisdiction aliases
        # (handled separately below)

        # Check document type aliases
        if word in DOC_TYPE_ALIASES and document_type is None:
            document_type = DOC_TYPE_ALIASES[word]
            continue

        query_words.append(word)

    # Check multi-word jurisdiction aliases
    lower_query = raw_clean.lower()
    for alias, jur in JURISDICTION_ALIASES.items():
        if " " in alias and alias in lower_query and jurisdiction is None:
            jurisdiction = jur
            # Remove the alias from query words
            for part in alias.split():
                if part in query_words:
                    query_words.remove(part)

    # Reconstruct search query
    search_query = " ".join(query_words).strip()

    # If everything was parsed as filters, use original query
    if not search_query:
        search_query = raw_query

    return {
        "query": search_query,
        "jurisdiction": jurisdiction,
        "document_type": document_type,
    }


@require_auth
async def enhanced_search_command(update, context):
    """Handle /search with enhanced NL parsing, filters, and pagination."""
    raw_query = " ".join(context.args) if context.args else ""
    if not raw_query:
        await update.message.reply_text(
            "Usage: /search <query>\n\n"
            "Examples:\n"
            "  /search FDA cybersecurity guidance\n"
            "  /search EU MDR documents\n"
            "  /search ISO 13485\n"
            "  /search what UK safety alerts do we have?\n\n"
            "Jurisdiction filters: FDA, EU, UK, ISO, Canada, TGA, PMDA, etc.\n"
            "Type filters: guidance, standard, regulation, advisory, etc."
        )
        return

    user_id = update.effective_user.id
    parsed = parse_query(raw_query)

    # Show what was parsed
    filter_parts = []
    if parsed["jurisdiction"]:
        filter_parts.append(f"jurisdiction={parsed['jurisdiction']}")
    if parsed["document_type"]:
        filter_parts.append(f"type={parsed['document_type']}")
    filter_note = f" ({', '.join(filter_parts)})" if filter_parts else ""

    await update.message.reply_text(f"🔍 Searching: {parsed['query']}{filter_note}...")

    try:
        from regkb.config import config

        limit = config.get("intelligence.telegram.search_limit", 5)
        results = await asyncio.to_thread(
            _run_filtered_search,
            parsed["query"],
            limit,
            parsed["jurisdiction"],
            parsed["document_type"],
        )

        if not results:
            # Try without filters if filtered search returned nothing
            if parsed["jurisdiction"] or parsed["document_type"]:
                results = await asyncio.to_thread(
                    _run_filtered_search, raw_query, limit, None, None
                )
                if results:
                    filter_note = " (broadened — no filter match)"

        if not results:
            await update.message.reply_text("No results found. Try broader search terms.")
            return

        # Store context for follow-up
        _search_context[user_id] = {
            "query": raw_query,
            "parsed": parsed,
            "results": results,
            "page": 0,
        }

        text = _format_enhanced_results(results, parsed["query"], filter_note)

        from regkb.telegram.keyboards import _build_search_keyboard

        keyboard = _build_search_keyboard(
            page=0,
            has_more=len(results) >= limit,
            total=len(results),
        )
        await _safe_reply_search(update, text, reply_markup=keyboard)

    except Exception as e:
        logger.exception("Enhanced search failed")
        await update.message.reply_text(f"Search error: {e}")


@require_auth
async def ask_command(update, context):
    """Handle /ask <question> — natural language question about the KB.

    Routes to local LLM if available, otherwise falls back to search.
    """
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text(
            "Usage: /ask <question>\n\n"
            "Examples:\n"
            "  /ask What FDA cybersecurity guidance do we have?\n"
            "  /ask How many EU regulations are in the KB?\n"
            "  /ask What's the latest on MDR?"
        )
        return

    try:
        from regkb.telegram.llm_handler import answer_question

        await update.message.reply_text("🤔 Thinking...")
        answer = await answer_question(question)
        await update.message.reply_text(answer)
    except ImportError:
        # No LLM handler available — fall back to search
        context.args = question.split()
        await enhanced_search_command(update, context)
    except Exception as e:
        logger.exception("Ask command failed")
        await update.message.reply_text(f"Error: {e}")


async def handle_search_callback(query, data: str):
    """Handle search-related callback queries (pagination, details)."""
    user_id = query.from_user.id
    ctx = _search_context.get(user_id)

    if not ctx:
        await query.edit_message_text("Search context expired. Run /search again.")
        return

    if data.startswith("search_page_"):
        page = int(data.split("_")[2])
        await _show_search_page(query, ctx, page)
    elif data.startswith("search_detail_"):
        idx = int(data.split("_")[2])
        await _show_detail(query, ctx, idx)
    elif data == "search_back":
        await _show_search_page(query, ctx, ctx.get("page", 0))


async def _show_search_page(query, ctx: dict, page: int):
    """Show a specific page of search results."""
    from regkb.config import config

    limit = config.get("intelligence.telegram.search_limit", 5)
    results = ctx["results"]
    start = page * limit
    end = start + limit
    page_results = results[start:end]

    if not page_results:
        await query.edit_message_text("No more results.")
        return

    ctx["page"] = page
    text = _format_enhanced_results(page_results, ctx["parsed"]["query"], f" (page {page + 1})")

    from regkb.telegram.keyboards import _build_search_keyboard

    keyboard = _build_search_keyboard(
        page=page,
        has_more=end < len(results),
        total=len(results),
    )

    try:
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
    except Exception:
        await query.edit_message_text(
            f"Search results page {page + 1}",
            reply_markup=keyboard,
        )


async def _show_detail(query, ctx: dict, idx: int):
    """Show detailed view of a single search result."""
    results = ctx["results"]
    if idx >= len(results):
        await query.edit_message_text("Result not found.")
        return

    result = results[idx]
    parts = [f"📄 {bold(escape_md(result.get('title', 'Untitled')))}"]

    for field in ("jurisdiction", "document_type", "version"):
        val = result.get(field)
        if val:
            parts.append(f"{escape_md(field.replace('_', ' ').title())}: {escape_md(str(val))}")

    desc = result.get("description", "")
    if desc:
        parts.append(f"\n{escape_md(desc[:500])}")

    excerpt = result.get("excerpt", "")
    if excerpt:
        parts.append(f"\n{escape_md('--- Excerpt ---')}")
        parts.append(escape_md(excerpt[:800]))

    score = result.get("score") or result.get("similarity")
    if score:
        parts.append(f"\nRelevance: {escape_md(f'{score:.0%}')}")

    text = "\n".join(parts)

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="search_back")]])

    try:
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
    except Exception:
        await query.edit_message_text(
            result.get("title", "Detail view"),
            reply_markup=keyboard,
        )


def _format_enhanced_results(results: list[dict], query: str, suffix: str = "") -> str:
    """Format search results with detail buttons."""
    parts = [f"🔍 {bold('Search')}: {escape_md(query)}{escape_md(suffix)}", ""]

    for i, result in enumerate(results):
        parts.append(format_search_result(result, i))
        parts.append("")

    parts.append(escape_md(f"{len(results)} result(s) — tap a number for details"))
    return "\n".join(parts)


def _run_filtered_search(
    query: str,
    limit: int = 5,
    jurisdiction: Optional[str] = None,
    document_type: Optional[str] = None,
) -> list[dict]:
    """Run filtered search against the KB."""
    from regkb.search import SearchEngine

    engine = SearchEngine()
    return engine.search(
        query,
        limit=limit,
        jurisdiction=jurisdiction,
        document_type=document_type,
    )


async def _safe_reply_search(update, text: str, **kwargs):
    """Send search reply, falling back to plain text."""
    try:
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH]
        await update.message.reply_text(text, parse_mode="MarkdownV2", **kwargs)
    except Exception:
        logger.warning("MarkdownV2 failed in search reply, falling back to plain text")
        plain = text.replace("\\", "")
        await update.message.reply_text(plain[:MAX_MESSAGE_LENGTH])
