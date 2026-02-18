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
    from telegram.ext import (
        ApplicationBuilder,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    from regkb.telegram.callbacks import handle_callback
    from regkb.telegram.handlers import (
        digest_command,
        help_command,
        pending_command,
        start_command,
        status_command,
    )
    from regkb.telegram.notifications import set_bot
    from regkb.telegram.search_handler import ask_command, enhanced_search_command

    application = ApplicationBuilder().token(token).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("digest", digest_command))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(CommandHandler("search", enhanced_search_command))
    application.add_handler(CommandHandler("ask", ask_command))

    # Register callback query handler for inline keyboards
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Handle plain text messages as natural language questions
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_message))

    # Set bot reference for notifications module
    set_bot(application.bot)

    logger.info("Telegram bot configured with 7 command handlers + NL message handler")
    return application


async def _handle_text_message(update, context):
    """Route plain text messages to /ask handler."""
    from regkb.telegram.auth import get_authorized_users

    user = update.effective_user
    if not user:
        return

    authorized = get_authorized_users()
    if authorized and user.id not in authorized:
        return  # Silently ignore unauthorized plain text

    # Treat as natural language question
    context.args = update.message.text.split()

    from regkb.telegram.search_handler import ask_command

    await ask_command(update, context)
