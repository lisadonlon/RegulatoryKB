"""
FastAPI lifespan context manager.

Starts/stops APScheduler and Telegram bot alongside the web server.
Both are optional — if tokens/config aren't set, they're skipped gracefully.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown of scheduler and Telegram bot."""
    app.state.started_at = datetime.now()
    app.state.scheduler = None
    app.state.telegram_app = None

    # Start APScheduler if enabled
    scheduler = _start_scheduler()
    if scheduler:
        app.state.scheduler = scheduler

    # Start Telegram bot if token is configured
    telegram_app = await _start_telegram_bot()
    if telegram_app:
        app.state.telegram_app = telegram_app

    logger.info(
        "RegKB started: scheduler=%s, telegram=%s",
        scheduler is not None,
        telegram_app is not None,
    )

    yield

    # Shutdown
    if app.state.telegram_app:
        try:
            await app.state.telegram_app.stop()
            await app.state.telegram_app.shutdown()
            logger.info("Telegram bot stopped")
        except Exception:
            logger.exception("Error stopping Telegram bot")

    if app.state.scheduler:
        try:
            app.state.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
        except Exception:
            logger.exception("Error stopping scheduler")

    logger.info("RegKB shutdown complete")


def _start_scheduler():
    """Start APScheduler if the bot extras are installed and scheduler is enabled."""
    try:
        from regkb.config import config

        scheduler_config = config.get("intelligence.scheduler", {})
        if not scheduler_config.get("enabled", False):
            logger.info("Scheduler disabled in config")
            return None

        from regkb.scheduler.setup import create_scheduler

        scheduler = create_scheduler()
        scheduler.start()
        logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
        return scheduler
    except ImportError:
        logger.info("APScheduler not installed — install with: pip install -e '.[bot]'")
        return None
    except Exception:
        logger.exception("Failed to start scheduler")
        return None


async def _start_telegram_bot():
    """Start Telegram bot if token is configured."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled")
        return None

    try:
        from regkb.telegram.bot import create_bot

        application = create_bot(token)
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started (polling mode)")
        return application
    except ImportError:
        logger.info("python-telegram-bot not installed — install with: pip install -e '.[bot]'")
        return None
    except Exception:
        logger.exception("Failed to start Telegram bot")
        return None
