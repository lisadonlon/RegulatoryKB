"""
Telegram bot factory — creates and configures the Application with all handlers.
"""

import logging

logger = logging.getLogger(__name__)


def create_bot(token: str):
    """Create a Telegram bot Application with all command handlers registered.

    Args:
        token: Telegram bot token from @BotFather.

    Returns:
        telegram.ext.Application ready to be started.
    """
    from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

    from regkb.telegram.callbacks import handle_callback
    from regkb.telegram.handlers import (
        digest_command,
        help_command,
        pending_command,
        search_command,
        start_command,
        status_command,
    )
    from regkb.telegram.notifications import set_bot

    application = ApplicationBuilder().token(token).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("digest", digest_command))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(CommandHandler("search", search_command))

    # Register callback query handler for inline keyboards
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Set bot reference for notifications module
    set_bot(application.bot)

    logger.info("Telegram bot configured with 6 command handlers")
    return application
