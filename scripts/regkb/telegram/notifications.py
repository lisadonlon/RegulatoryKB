"""
Telegram push notification module.

The bot reference is set during lifespan startup.
Notifications are fire-and-forget — failures are logged but don't propagate.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Module-level bot reference, set by lifespan
_bot = None


def set_bot(bot):
    """Set the bot instance for sending notifications. Called during lifespan startup."""
    global _bot
    _bot = bot


def _get_chat_ids() -> list[int]:
    """Get authorized user IDs to send notifications to."""
    raw = os.environ.get("TELEGRAM_AUTHORIZED_USERS", "")
    if not raw.strip():
        return []
    try:
        return [int(uid.strip()) for uid in raw.split(",") if uid.strip()]
    except ValueError:
        return []


async def notify_critical_alert(title: str, agency: str = ""):
    """Send immediate notification for critical regulatory alerts."""
    if not _bot:
        logger.debug("Telegram bot not configured — skipping critical alert notification")
        return

    message = f"🔴 CRITICAL ALERT\n\n{title}"
    if agency:
        message += f"\nAgency: {agency}"

    for chat_id in _get_chat_ids():
        try:
            await _bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            logger.exception("Failed to send critical alert to %d", chat_id)


async def notify_job_failure(job_id: str, error: str):
    """Send notification when a scheduled job fails."""
    if not _bot:
        return

    message = f"⚠️ Job Failed: {job_id}\n\nError: {error[:500]}"

    for chat_id in _get_chat_ids():
        try:
            await _bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            logger.exception("Failed to send job failure notification to %d", chat_id)


async def notify_digest_sent(entry_count: int, recipients: int):
    """Send notification after digest email is sent."""
    if not _bot:
        return

    message = f"📧 Digest sent: {entry_count} entries to {recipients} recipient(s)"

    for chat_id in _get_chat_ids():
        try:
            await _bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            logger.exception("Failed to send digest notification to %d", chat_id)


async def notify_notebooklm_auth_failure(job_name: str):
    """Send notification when NotebookLM auth has expired and needs re-authentication."""
    if not _bot:
        logger.debug("Telegram bot not configured — skipping auth failure notification")
        return

    message = (
        f"🔑 NotebookLM Auth Expired\n\n"
        f"Job: {job_name}\n"
        f"Action: Run `notebooklm login` in PowerShell to re-authenticate."
    )

    for chat_id in _get_chat_ids():
        try:
            await _bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            logger.exception("Failed to send auth failure notification to %d", chat_id)


async def notify_new_pending(count: int):
    """Notify about new items added to pending queue."""
    if not _bot:
        return

    message = f"📥 {count} new item(s) added to pending downloads.\nUse /pending to review."

    for chat_id in _get_chat_ids():
        try:
            await _bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            logger.exception("Failed to send pending notification to %d", chat_id)
