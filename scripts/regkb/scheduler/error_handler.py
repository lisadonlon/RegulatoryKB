"""
APScheduler error handler — logs failures and sends Telegram notifications.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


def job_error_listener(event):
    """Handle APScheduler EVENT_JOB_ERROR events.

    Logs the error and attempts to send a Telegram notification.
    """
    job_id = event.job_id
    exception = event.exception
    traceback_str = str(event.traceback) if event.traceback else ""

    logger.error(
        "Scheduled job '%s' failed: %s\n%s",
        job_id,
        exception,
        traceback_str,
    )

    # Fire-and-forget Telegram notification
    try:
        from regkb.telegram.notifications import notify_job_failure

        error_msg = f"{exception}"
        if traceback_str:
            error_msg += f"\n{traceback_str[:300]}"

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(notify_job_failure(job_id, error_msg))
        else:
            loop.run_until_complete(notify_job_failure(job_id, error_msg))
    except ImportError:
        pass  # Telegram not installed
    except Exception:
        logger.debug("Failed to send Telegram notification for job error", exc_info=True)
