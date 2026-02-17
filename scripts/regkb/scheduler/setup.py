"""
APScheduler factory — creates and configures the scheduler with all jobs.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from regkb.config import config

logger = logging.getLogger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    """Create an AsyncIOScheduler with all intelligence pipeline jobs configured.

    Reads schedule config from config.yaml under intelligence.schedule.
    Jobs use misfire_grace_time=3600 to handle laptop sleep/wake.

    Returns:
        Configured AsyncIOScheduler (not yet started).
    """
    timezone = config.get("intelligence.scheduler.timezone", "Europe/Dublin")
    scheduler = AsyncIOScheduler(timezone=timezone)

    _add_weekly_digest_job(scheduler)
    _add_daily_alert_job(scheduler)
    _add_imap_poll_job(scheduler)

    # Register error handler
    from regkb.scheduler.error_handler import job_error_listener

    scheduler.add_listener(job_error_listener, mask=64)  # EVENT_JOB_ERROR = 64

    logger.info(
        "Scheduler configured with %d jobs (timezone=%s)", len(scheduler.get_jobs()), timezone
    )
    return scheduler


def _add_weekly_digest_job(scheduler: AsyncIOScheduler) -> None:
    """Add weekly digest job based on config."""
    from regkb.scheduler.jobs import weekly_digest_job

    weekly_day = config.get("intelligence.schedule.weekly_day", "monday")
    weekly_time = config.get("intelligence.schedule.weekly_time", "08:00")
    hour, minute = _parse_time(weekly_time)

    scheduler.add_job(
        weekly_digest_job,
        CronTrigger(day_of_week=_day_to_cron(weekly_day), hour=hour, minute=minute),
        id="weekly_digest",
        name="Weekly Regulatory Digest",
        misfire_grace_time=3600,
        replace_existing=True,
    )
    logger.info("Weekly digest scheduled: %s at %s", weekly_day, weekly_time)


def _add_daily_alert_job(scheduler: AsyncIOScheduler) -> None:
    """Add daily alert job if enabled."""
    daily_enabled = config.get("intelligence.schedule.daily_alerts", True)
    if not daily_enabled:
        return

    from regkb.scheduler.jobs import daily_alert_job

    alert_time = config.get("intelligence.schedule.daily_alert_time", "09:00")
    hour, minute = _parse_time(alert_time)

    scheduler.add_job(
        daily_alert_job,
        CronTrigger(hour=hour, minute=minute),
        id="daily_alert",
        name="Daily Critical Alert Check",
        misfire_grace_time=3600,
        replace_existing=True,
    )
    logger.info("Daily alert scheduled at %s", alert_time)


def _add_imap_poll_job(scheduler: AsyncIOScheduler) -> None:
    """Add IMAP polling job."""
    from regkb.scheduler.jobs import imap_poll_job

    poll_interval = config.get("intelligence.reply_processing.poll_interval", 30)

    scheduler.add_job(
        imap_poll_job,
        IntervalTrigger(minutes=poll_interval),
        id="imap_poll",
        name="IMAP Reply Poll",
        misfire_grace_time=3600,
        replace_existing=True,
    )
    logger.info("IMAP poll scheduled every %d minutes", poll_interval)


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' string to (hour, minute) tuple."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0


def _day_to_cron(day: str) -> str:
    """Convert day name to APScheduler cron day_of_week value."""
    mapping = {
        "monday": "mon",
        "tuesday": "tue",
        "wednesday": "wed",
        "thursday": "thu",
        "friday": "fri",
        "saturday": "sat",
        "sunday": "sun",
    }
    return mapping.get(day.lower(), day.lower()[:3])
