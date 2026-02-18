"""
Telegram bot command handlers.

All pipeline calls are wrapped in asyncio.to_thread() since existing
RegKB modules are synchronous.
"""

import asyncio
import logging

from regkb.telegram.auth import require_auth
from regkb.telegram.formatters import (
    bold,
    escape_md,
    format_digest,
    format_pending_item,
    format_search_results,
    format_stats,
)

logger = logging.getLogger(__name__)

# Maximum Telegram message length
MAX_MESSAGE_LENGTH = 4096


async def _safe_reply(update, text: str, parse_mode: str = "MarkdownV2", **kwargs):
    """Send reply, falling back to plain text if MarkdownV2 fails."""
    try:
        if len(text) > MAX_MESSAGE_LENGTH:
            # Split long messages
            for i in range(0, len(text), MAX_MESSAGE_LENGTH):
                chunk = text[i : i + MAX_MESSAGE_LENGTH]
                await update.message.reply_text(chunk, parse_mode=parse_mode, **kwargs)
        else:
            await update.message.reply_text(text, parse_mode=parse_mode, **kwargs)
    except Exception:
        # Fallback to plain text if markdown parsing fails
        logger.warning("MarkdownV2 failed, falling back to plain text")
        plain = text.replace("\\", "")
        await update.message.reply_text(plain[:MAX_MESSAGE_LENGTH])


async def start_command(update, context):
    """Handle /start command."""
    text = (
        f"👋 {bold('Welcome to RegKB')}\n\n"
        f"{escape_md('Regulatory Intelligence Assistant for medical device professionals.')}\n\n"
        f"{escape_md('Commands:')}\n"
        f"/status {escape_md('— KB stats and pipeline status')}\n"
        f"/digest {escape_md('— Run pipeline and show latest updates')}\n"
        f"/pending {escape_md('— View pending downloads')}\n"
        f"/search {escape_md('<query> — Search with filters')}\n"
        f"/ask {escape_md('<question> — Ask about KB contents')}\n"
        f"/help {escape_md('— Show this help message')}\n\n"
        f"{escape_md('Or just type a question directly!')}\n"
    )
    await _safe_reply(update, text)


async def help_command(update, context):
    """Handle /help command."""
    text = (
        f"📖 {bold('RegKB Commands')}\n\n"
        f"/status {escape_md('— Knowledge base statistics, pending count, scheduler status')}\n"
        f"/digest {escape_md('— Fetch latest regulatory updates and display summary')}\n"
        f"/pending {escape_md('— Show pending downloads with approve/reject buttons')}\n"
        f"/search {escape_md('<query> — Search KB with jurisdiction/type filters')}\n"
        f"/ask {escape_md('<question> — Ask questions about KB contents (LLM-powered)')}\n"
        f"/help {escape_md('— This help message')}\n\n"
        f"{escape_md('You can also type questions directly without a command.')}\n"
        f"{escape_md('Search understands jurisdictions: FDA, EU, UK, ISO, etc.')}\n"
        f"{escape_md('Inline buttons let you approve/reject items and paginate results.')}\n"
        f"{escape_md('Critical alerts are sent automatically via push notifications.')}"
    )
    await _safe_reply(update, text)


@require_auth
async def status_command(update, context):
    """Handle /status — show KB stats and pipeline status."""
    await update.message.reply_text("⏳ Loading status...")

    try:
        db_stats = await asyncio.to_thread(_get_db_stats)
        pending_count = await asyncio.to_thread(_get_pending_count)
        text = format_stats(db_stats, pending_count)
        await _safe_reply(update, text)
    except Exception as e:
        logger.exception("Status command failed")
        await update.message.reply_text(f"Error: {e}")


@require_auth
async def digest_command(update, context):
    """Handle /digest — run fetch+filter pipeline and show results."""
    await update.message.reply_text("⏳ Fetching regulatory updates...")

    try:
        entries = await asyncio.to_thread(_run_digest_pipeline)

        if not entries:
            await update.message.reply_text("No relevant regulatory updates found.")
            return

        text = format_digest(entries)

        from regkb.telegram.keyboards import digest_action_keyboard

        await _safe_reply(update, text, reply_markup=digest_action_keyboard())
    except Exception as e:
        logger.exception("Digest command failed")
        await update.message.reply_text(f"Error running digest: {e}")


@require_auth
async def pending_command(update, context):
    """Handle /pending — show pending downloads with approve/reject buttons."""
    try:
        from regkb.config import config

        page_size = config.get("intelligence.telegram.pending_page_size", 5)
        items = await asyncio.to_thread(_get_pending_items)

        if not items:
            await update.message.reply_text("No pending downloads.")
            return

        page_items = items[:page_size]
        parts = [f"⏳ {bold('Pending Downloads')} ({escape_md(str(len(items)))} total)\n"]

        from regkb.telegram.keyboards import pending_item_keyboard, pending_list_keyboard

        # Send each item as a separate message with inline keyboard
        await _safe_reply(update, "\n".join(parts))

        for i, item in enumerate(page_items):
            item_id = getattr(item, "id", None) or (item.get("id") if isinstance(item, dict) else i)
            text = format_pending_item(item, i)
            try:
                await update.message.reply_text(
                    text,
                    parse_mode="MarkdownV2",
                    reply_markup=pending_item_keyboard(item_id),
                )
            except Exception:
                await update.message.reply_text(
                    f"#{i + 1} (formatting error)",
                    reply_markup=pending_item_keyboard(item_id),
                )

        has_more = len(items) > page_size
        if has_more:
            await update.message.reply_text(
                escape_md(f"Showing {page_size} of {len(items)}"),
                parse_mode="MarkdownV2",
                reply_markup=pending_list_keyboard(page=0, has_next=True),
            )
    except Exception as e:
        logger.exception("Pending command failed")
        await update.message.reply_text(f"Error: {e}")


@require_auth
async def search_command(update, context):
    """Handle /search <query> — search the knowledge base."""
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            "Usage: /search <query>\nExample: /search FDA cybersecurity guidance"
        )
        return

    try:
        from regkb.config import config

        limit = config.get("intelligence.telegram.search_limit", 5)
        results = await asyncio.to_thread(_run_search, query, limit)
        text = format_search_results(results, query)
        await _safe_reply(update, text)
    except Exception as e:
        logger.exception("Search command failed")
        await update.message.reply_text(f"Search error: {e}")


# --- Pipeline helper functions (run in thread) ---


def _get_db_stats() -> dict:
    """Get database statistics."""
    from regkb.database import Database

    db = Database()
    return db.get_statistics()


def _get_pending_count() -> int:
    """Get count of pending downloads."""
    from regkb.intelligence.analyzer import KBAnalyzer

    analyzer = KBAnalyzer()
    stats = analyzer.get_stats()
    return stats.get("pending", 0)


def _get_pending_items() -> list:
    """Get pending download items."""
    from regkb.intelligence.analyzer import KBAnalyzer

    analyzer = KBAnalyzer()
    return analyzer.get_pending("pending")


def _run_digest_pipeline() -> list:
    """Run fetch + filter pipeline, return filtered entries."""
    from regkb.intelligence.fetcher import NewsletterFetcher
    from regkb.intelligence.filter import ContentFilter

    fetcher = NewsletterFetcher()
    fetch_result = fetcher.fetch(days=7)

    content_filter = ContentFilter()
    filter_result = content_filter.filter(fetch_result.entries)

    return filter_result.included


def _run_search(query: str, limit: int = 5) -> list[dict]:
    """Run search against the knowledge base."""
    from regkb.search import SearchEngine

    engine = SearchEngine()
    return engine.search(query, limit=limit)


def _approve_item(item_id: int) -> bool:
    """Approve a pending download item."""
    from regkb.intelligence.analyzer import KBAnalyzer

    analyzer = KBAnalyzer()
    count = analyzer.approve([item_id])
    return count > 0


def _reject_item(item_id: int) -> bool:
    """Reject a pending download item."""
    from regkb.intelligence.analyzer import KBAnalyzer

    analyzer = KBAnalyzer()
    count = analyzer.reject([item_id])
    return count > 0
