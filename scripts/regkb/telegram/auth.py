"""
Telegram bot authentication — restrict access to authorized users.
"""

import logging
import os
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def get_authorized_users() -> set[int]:
    """Load authorized Telegram user IDs from environment."""
    raw = os.environ.get("TELEGRAM_AUTHORIZED_USERS", "")
    if not raw.strip():
        return set()
    try:
        return {int(uid.strip()) for uid in raw.split(",") if uid.strip()}
    except ValueError:
        logger.error("Invalid TELEGRAM_AUTHORIZED_USERS format: %s", raw)
        return set()


def require_auth(func: Callable) -> Callable:
    """Decorator to restrict Telegram handler to authorized users only."""

    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        authorized = get_authorized_users()
        if not authorized:
            logger.warning("No authorized users configured — denying all access")
            await update.message.reply_text("Bot not configured. Set TELEGRAM_AUTHORIZED_USERS.")
            return

        if user.id not in authorized:
            logger.warning("Unauthorized access attempt from user %d (%s)", user.id, user.username)
            await update.message.reply_text("You are not authorized to use this bot.")
            return

        return await func(update, context, *args, **kwargs)

    return wrapper
