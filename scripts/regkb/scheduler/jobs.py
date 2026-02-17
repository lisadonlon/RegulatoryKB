"""
Scheduled job definitions for the RegKB intelligence pipeline.

All jobs are async functions that wrap synchronous pipeline calls
in asyncio.to_thread(). Each job checks SchedulerState for idempotency.
"""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def weekly_digest_job():
    """Fetch, filter, and send weekly digest via email and Telegram.

    Uses SchedulerState.should_run_weekly() for idempotency — if the digest
    was already sent this week (e.g., manual trigger), this is a no-op.
    """
    logger.info("Weekly digest job started")

    def _run():
        from regkb.intelligence.scheduler import SchedulerState

        state = SchedulerState()
        if not state.should_run_weekly():
            logger.info("Weekly digest already sent this period — skipping")
            return None

        from regkb.intelligence.fetcher import NewsletterFetcher
        from regkb.intelligence.filter import ContentFilter

        # Try multi-source if available, fallback to newsletter only
        try:
            from regkb.intelligence.sources.registry import fetch_all_sources

            fetch_result = fetch_all_sources(days=7)
        except ImportError:
            fetcher = NewsletterFetcher()
            fetch_result = fetcher.fetch(days=7)

        content_filter = ContentFilter()
        filter_result = content_filter.filter(fetch_result.entries)

        if filter_result.total_included == 0:
            logger.info("No relevant entries for weekly digest")
            state.mark_weekly_run()
            return None

        # Send email
        from regkb.intelligence.emailer import Emailer

        emailer = Emailer()
        entries_with_summaries = [(fe, None) for fe in filter_result.included]
        high_priority = [(fe, None) for fe in filter_result.high_priority]

        end = datetime.now()
        start = end - timedelta(days=7)
        date_range = f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"

        email_result = emailer.send_weekly_digest(
            entries_with_summaries=entries_with_summaries,
            high_priority=high_priority,
            date_range=date_range,
        )

        state.mark_weekly_run()
        return {
            "entries": filter_result.total_included,
            "email_success": email_result.success,
            "recipients": email_result.recipients_sent,
        }

    result = await asyncio.to_thread(_run)

    if result:
        logger.info(
            "Weekly digest complete: %d entries, email=%s, recipients=%d",
            result["entries"],
            result["email_success"],
            result["recipients"],
        )

        # Send Telegram notification
        try:
            from regkb.telegram.notifications import notify_digest_sent

            await notify_digest_sent(result["entries"], result["recipients"])
        except ImportError:
            pass


async def daily_alert_job():
    """Check for critical/high-priority items and send alerts.

    Only sends if new critical items are found since last daily run.
    """
    logger.info("Daily alert job started")

    def _run():
        from regkb.intelligence.scheduler import SchedulerState

        state = SchedulerState()
        if not state.should_run_daily():
            logger.info("Daily alert already run today — skipping")
            return None

        from regkb.intelligence.fetcher import NewsletterFetcher
        from regkb.intelligence.filter import ContentFilter

        # Try multi-source if available
        try:
            from regkb.intelligence.sources.registry import fetch_all_sources

            fetch_result = fetch_all_sources(days=1)
        except ImportError:
            fetcher = NewsletterFetcher()
            fetch_result = fetcher.fetch(days=1)

        content_filter = ContentFilter()
        filter_result = content_filter.filter(fetch_result.entries)

        state.mark_daily_run()

        critical = [e for e in filter_result.included if e.alert_level in ("CRITICAL", "HIGH")]
        return critical

    critical = await asyncio.to_thread(_run)

    if critical:
        logger.info("Daily alert: %d critical/high items found", len(critical))

        # Send Telegram push for each critical item
        try:
            from regkb.telegram.notifications import notify_critical_alert

            for entry in critical:
                await notify_critical_alert(
                    title=entry.entry.title,
                    agency=entry.entry.agency or "",
                )
        except ImportError:
            pass
    else:
        logger.info("Daily alert: no critical items")


async def imap_poll_job():
    """Poll IMAP inbox for download request replies."""
    logger.info("IMAP poll job started")

    def _run():
        import os

        # Check if IMAP credentials are configured
        if not os.environ.get("IMAP_USERNAME"):
            logger.debug("IMAP not configured — skipping poll")
            return None

        from regkb.intelligence.reply_handler import ReplyHandler

        handler = ReplyHandler()
        result = handler.process_all_pending()
        return result

    result = await asyncio.to_thread(_run)

    if result:
        logger.info("IMAP poll complete: %s", result)
