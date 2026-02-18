"""
Telegram callback query handlers for inline keyboard interactions.
"""

import asyncio
import logging

from regkb.telegram.auth import get_authorized_users
from regkb.telegram.formatters import bold, escape_md
from regkb.telegram.handlers import _approve_item, _get_pending_items, _reject_item

logger = logging.getLogger(__name__)


async def handle_callback(update, context):
    """Route callback queries to the appropriate handler."""
    query = update.callback_query
    if not query:
        return

    # Auth check
    user = query.from_user
    authorized = get_authorized_users()
    if authorized and user.id not in authorized:
        await query.answer("Unauthorized", show_alert=True)
        return

    await query.answer()  # Acknowledge the callback

    data = query.data
    if not data:
        return

    try:
        if data.startswith("approve_all"):
            await _handle_approve_all(query)
        elif data.startswith("approve_"):
            item_id = int(data.split("_", 1)[1])
            await _handle_approve(query, item_id)
        elif data.startswith("reject_"):
            item_id = int(data.split("_", 1)[1])
            await _handle_reject(query, item_id)
        elif data.startswith("page_"):
            page = int(data.split("_", 1)[1])
            await _handle_page(query, page)
        elif data == "show_pending":
            await _handle_show_pending(query)
        elif data == "send_email":
            await _handle_send_email(query)
        elif data == "refresh_digest":
            await _handle_refresh_digest(query)
        elif data.startswith("search_"):
            from regkb.telegram.search_handler import handle_search_callback

            await handle_search_callback(query, data)
        elif data == "cancel":
            await query.edit_message_reply_markup(reply_markup=None)
        else:
            logger.warning("Unknown callback data: %s", data)
    except Exception as e:
        logger.exception("Callback handler error for data=%s", data)
        await query.edit_message_text(f"Error: {e}")


async def _handle_approve(query, item_id: int):
    """Approve a single pending download."""
    success = await asyncio.to_thread(_approve_item, item_id)
    if success:
        await query.edit_message_text(f"✅ Item #{item_id} approved")
    else:
        await query.edit_message_text(f"Failed to approve item #{item_id}")


async def _handle_reject(query, item_id: int):
    """Reject a single pending download."""
    success = await asyncio.to_thread(_reject_item, item_id)
    if success:
        await query.edit_message_text(f"❌ Item #{item_id} rejected")
    else:
        await query.edit_message_text(f"Failed to reject item #{item_id}")


async def _handle_approve_all(query):
    """Approve all pending downloads."""
    from regkb.intelligence.analyzer import KBAnalyzer

    def _do_approve_all():
        analyzer = KBAnalyzer()
        return analyzer.approve_all()

    count = await asyncio.to_thread(_do_approve_all)
    await query.edit_message_text(f"✅ Approved {count} item(s)")


async def _handle_page(query, page: int):
    """Show a specific page of pending items."""
    from regkb.config import config
    from regkb.telegram.formatters import format_pending_item
    from regkb.telegram.keyboards import pending_list_keyboard

    page_size = config.get("intelligence.telegram.pending_page_size", 5)
    items = await asyncio.to_thread(_get_pending_items)

    start = page * page_size
    end = start + page_size
    page_items = items[start:end]

    if not page_items:
        await query.edit_message_text("No more items.")
        return

    parts = [f"⏳ {bold('Pending Downloads')} (page {escape_md(str(page + 1))})\n"]
    for i, item in enumerate(page_items):
        parts.append(format_pending_item(item, start + i))
        parts.append("")

    text = "\n".join(parts)
    has_next = end < len(items)
    has_prev = page > 0

    try:
        await query.edit_message_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=pending_list_keyboard(page, has_next, has_prev),
        )
    except Exception:
        await query.edit_message_text(
            f"Pending items page {page + 1}",
            reply_markup=pending_list_keyboard(page, has_next, has_prev),
        )


async def _handle_show_pending(query):
    """Switch from digest view to pending view."""
    items = await asyncio.to_thread(_get_pending_items)
    count = len(items)
    await query.edit_message_text(
        f"⏳ {count} pending download(s). Use /pending to view with action buttons."
    )


async def _handle_send_email(query):
    """Trigger email digest send."""
    await query.edit_message_text("📧 Sending digest email...")

    try:
        from regkb.telegram.handlers import _run_digest_pipeline

        def _send():
            from datetime import datetime, timedelta

            from regkb.intelligence.emailer import Emailer

            entries = _run_digest_pipeline()
            if not entries:
                return False, "No entries to send"

            emailer = Emailer()
            entries_with_summaries = [(e, None) for e in entries]
            high_priority = [(e, None) for e in entries if e.alert_level in ("CRITICAL", "HIGH")]

            end = datetime.now()
            start = end - timedelta(days=7)
            date_range = f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"

            result = emailer.send_weekly_digest(
                entries_with_summaries=entries_with_summaries,
                high_priority=high_priority,
                date_range=date_range,
            )
            return result.success, result.error or f"Sent to {result.recipients_sent} recipient(s)"

        success, message = await asyncio.to_thread(_send)
        if success:
            await query.edit_message_text(f"✅ Email digest sent: {message}")
        else:
            await query.edit_message_text(f"❌ Email failed: {message}")
    except Exception as e:
        logger.exception("Send email callback failed")
        await query.edit_message_text(f"❌ Error: {e}")


async def _handle_refresh_digest(query):
    """Re-run digest pipeline and update message."""
    await query.edit_message_text("🔄 Refreshing...")

    try:
        from regkb.telegram.formatters import format_digest
        from regkb.telegram.handlers import _run_digest_pipeline
        from regkb.telegram.keyboards import digest_action_keyboard

        entries = await asyncio.to_thread(_run_digest_pipeline)
        text = format_digest(entries)
        await query.edit_message_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=digest_action_keyboard(),
        )
    except Exception as e:
        logger.exception("Refresh digest failed")
        await query.edit_message_text(f"Error: {e}")
