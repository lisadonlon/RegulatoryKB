"""
Intelligence pipeline management routes.
"""

import logging
import traceback

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from regkb.database import Database
from regkb.intelligence.analyzer import KBAnalyzer
from regkb.intelligence.digest_tracker import DigestTracker
from regkb.intelligence.emailer import Emailer
from regkb.intelligence.fetcher import NewsletterFetcher
from regkb.intelligence.filter import ContentFilter
from regkb.intelligence.scheduler import SchedulerState
from regkb.web.dependencies import flash, get_db, get_flashed_messages

router = APIRouter(tags=["intel"])
templates = Jinja2Templates(directory="scripts/regkb/web/templates")


def get_analyzer() -> KBAnalyzer:
    return KBAnalyzer()


def get_digest_tracker() -> DigestTracker:
    return DigestTracker()


def get_scheduler() -> SchedulerState:
    return SchedulerState()


@router.get("/intel", response_class=HTMLResponse)
async def intel_dashboard(
    request: Request,
    db: Database = Depends(get_db),
):
    """Intelligence pipeline dashboard."""
    analyzer = get_analyzer()
    digest_tracker = get_digest_tracker()
    scheduler = get_scheduler()

    pending_stats = analyzer.get_stats()
    digest_stats = digest_tracker.get_stats()

    # Get recent pending items
    pending_items = analyzer.get_pending("pending")[:5]

    # Get recent digests
    recent_entries = digest_tracker.get_recent_entries(limit=10)

    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "intel",
        "pending_stats": pending_stats,
        "digest_stats": digest_stats,
        "pending_items": pending_items,
        "recent_entries": recent_entries,
        "scheduler": scheduler,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("intel.html", context)


@router.get("/intel/pending", response_class=HTMLResponse)
async def intel_pending(
    request: Request,
    status: str = "pending",
    db: Database = Depends(get_db),
):
    """Pending downloads queue."""
    analyzer = get_analyzer()
    pending_items = analyzer.get_pending(status)
    pending_stats = analyzer.get_stats()
    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "intel",
        "pending_items": pending_items,
        "pending_stats": pending_stats,
        "current_status": status,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("intel_pending.html", context)


@router.post("/intel/pending/approve", response_class=HTMLResponse)
async def intel_approve(
    request: Request,
):
    """Approve selected pending downloads."""
    form = await request.form()
    ids = [int(id) for id in form.getlist("ids")]

    if not ids:
        flash(request, "No items selected", "warning")
    else:
        analyzer = get_analyzer()
        count = analyzer.approve(ids)
        flash(request, f"Approved {count} item(s)", "success")

    return RedirectResponse(url="/intel/pending", status_code=303)


@router.post("/intel/pending/reject", response_class=HTMLResponse)
async def intel_reject(
    request: Request,
):
    """Reject selected pending downloads."""
    form = await request.form()
    ids = [int(id) for id in form.getlist("ids")]

    if not ids:
        flash(request, "No items selected", "warning")
    else:
        analyzer = get_analyzer()
        count = analyzer.reject(ids)
        flash(request, f"Rejected {count} item(s)", "success")

    return RedirectResponse(url="/intel/pending", status_code=303)


@router.post("/intel/pending/approve-all", response_class=HTMLResponse)
async def intel_approve_all(
    request: Request,
):
    """Approve all pending downloads."""
    analyzer = get_analyzer()
    count = analyzer.approve_all()
    flash(request, f"Approved {count} item(s)", "success")
    return RedirectResponse(url="/intel/pending", status_code=303)


@router.get("/intel/digests", response_class=HTMLResponse)
async def intel_digests(
    request: Request,
    db: Database = Depends(get_db),
):
    """Digest history and entry tracking."""
    digest_tracker = get_digest_tracker()
    digest_stats = digest_tracker.get_stats()
    recent_entries = digest_tracker.get_recent_entries(limit=50)
    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "intel",
        "digest_stats": digest_stats,
        "recent_entries": recent_entries,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("intel_digests.html", context)


# Background task status
_pipeline_status = {
    "running": False,
    "stage": "",
    "message": "",
    "error": None,
}


def run_fetch_task():
    """Background task: fetch newsletter entries."""
    global _pipeline_status
    try:
        _pipeline_status["stage"] = "Fetching"
        _pipeline_status["message"] = "Fetching newsletter entries..."

        fetcher = NewsletterFetcher()
        result = fetcher.fetch(days=7)

        _pipeline_status["message"] = (
            f"Fetched {result.total_entries} entries from {result.sources_fetched} sources"
        )
    except Exception as e:
        _pipeline_status["error"] = str(e)
    finally:
        _pipeline_status["running"] = False


def run_sync_task():
    """Background task: full sync (fetch, filter, analyze)."""
    global _pipeline_status
    logger = logging.getLogger(__name__)
    try:
        _pipeline_status["stage"] = "Fetching"
        _pipeline_status["message"] = "Fetching newsletter entries..."

        fetcher = NewsletterFetcher()
        fetch_result = fetcher.fetch(days=7)

        _pipeline_status["stage"] = "Filtering"
        _pipeline_status["message"] = f"Filtering {fetch_result.total_entries} entries..."

        content_filter = ContentFilter()
        filter_result = content_filter.filter(fetch_result.entries)

        _pipeline_status["stage"] = "Analyzing"
        _pipeline_status["message"] = (
            f"Analyzing {filter_result.total_included} relevant entries..."
        )

        analyzer = KBAnalyzer()
        analysis = analyzer.analyze(filter_result.included)

        _pipeline_status["message"] = str(analysis)

        # Send Telegram notification about new pending items
        _notify_new_pending(analysis)
    except Exception as e:
        logger.error(f"Sync task failed:\n{traceback.format_exc()}")
        _pipeline_status["error"] = str(e)
    finally:
        _pipeline_status["running"] = False


@router.post("/intel/fetch", response_class=HTMLResponse)
async def intel_fetch(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Trigger newsletter fetch."""
    global _pipeline_status

    if _pipeline_status["running"]:
        flash(request, "Pipeline already running", "warning")
    else:
        _pipeline_status = {"running": True, "stage": "", "message": "", "error": None}
        background_tasks.add_task(run_fetch_task)
        flash(request, "Fetch started in background", "info")

    return RedirectResponse(url="/intel", status_code=303)


@router.post("/intel/sync", response_class=HTMLResponse)
async def intel_sync(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Run full sync (fetch, filter, analyze)."""
    global _pipeline_status

    if _pipeline_status["running"]:
        flash(request, "Pipeline already running", "warning")
    else:
        _pipeline_status = {"running": True, "stage": "", "message": "", "error": None}
        background_tasks.add_task(run_sync_task)
        flash(request, "Sync started in background", "info")

    return RedirectResponse(url="/intel", status_code=303)


def run_send_digest_task():
    """Background task: fetch, filter, and send digest email."""
    global _pipeline_status
    logger = logging.getLogger(__name__)
    try:
        from datetime import datetime, timedelta

        from dotenv import load_dotenv

        load_dotenv()

        _pipeline_status["stage"] = "Fetching"
        _pipeline_status["message"] = "Fetching newsletter entries..."

        fetcher = NewsletterFetcher()
        fetch_result = fetcher.fetch(days=14)

        _pipeline_status["stage"] = "Filtering"
        _pipeline_status["message"] = f"Filtering {fetch_result.total_entries} entries..."

        content_filter = ContentFilter()
        filter_result = content_filter.filter(fetch_result.entries)

        if filter_result.total_included == 0:
            _pipeline_status["message"] = "No relevant entries found to send."
            return

        _pipeline_status["stage"] = "Sending"
        _pipeline_status["message"] = (
            f"Sending digest with {filter_result.total_included} entries..."
        )

        emailer = Emailer()
        entries_with_summaries = [(fe, None) for fe in filter_result.included]
        high_priority = [(fe, None) for fe in filter_result.high_priority]

        end = datetime.now()
        start = end - timedelta(days=14)
        date_range = f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"

        email_result = emailer.send_weekly_digest(
            entries_with_summaries=entries_with_summaries,
            high_priority=high_priority,
            date_range=date_range,
        )

        if email_result.success:
            _pipeline_status["message"] = (
                f"Digest sent to {email_result.recipients_sent} recipient(s) "
                f"with {filter_result.total_included} entries"
            )
            # Send Telegram notification about digest delivery
            _notify_digest(filter_result.total_included, email_result.recipients_sent)
        else:
            _pipeline_status["error"] = f"Email failed: {email_result.error}"
    except Exception as e:
        logger.error(f"Send digest failed:\n{traceback.format_exc()}")
        _pipeline_status["error"] = str(e)
    finally:
        _pipeline_status["running"] = False


@router.post("/intel/send-digest", response_class=HTMLResponse)
async def intel_send_digest(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Fetch, filter, and send digest email."""
    global _pipeline_status

    if _pipeline_status["running"]:
        flash(request, "Pipeline already running", "warning")
    else:
        _pipeline_status = {"running": True, "stage": "", "message": "", "error": None}
        background_tasks.add_task(run_send_digest_task)
        flash(request, "Digest generation started in background", "info")

    return RedirectResponse(url="/intel", status_code=303)


_notify_logger = logging.getLogger(__name__)


def _notify_new_pending(analysis):
    """Fire-and-forget Telegram notification for new pending items."""
    try:
        import asyncio

        from regkb.telegram.notifications import notify_new_pending

        new_count = getattr(analysis, "new_downloadable", 0)
        if new_count > 0:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(notify_new_pending(new_count))
            else:
                loop.run_until_complete(notify_new_pending(new_count))
    except ImportError:
        pass  # Telegram not installed
    except Exception:
        _notify_logger.debug("Telegram notification failed (non-critical)", exc_info=True)


def _notify_digest(entry_count: int, recipients: int):
    """Fire-and-forget Telegram notification for digest delivery."""
    try:
        import asyncio

        from regkb.telegram.notifications import notify_digest_sent

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(notify_digest_sent(entry_count, recipients))
        else:
            loop.run_until_complete(notify_digest_sent(entry_count, recipients))
    except ImportError:
        pass  # Telegram not installed
    except Exception:
        _notify_logger.debug("Telegram notification failed (non-critical)", exc_info=True)


@router.get("/intel/status", response_class=HTMLResponse)
async def intel_status(request: Request):
    """Get current pipeline status (HTMX partial)."""
    global _pipeline_status

    if _pipeline_status["running"]:
        return HTMLResponse(
            f'<span aria-busy="true">{_pipeline_status["stage"]}: {_pipeline_status["message"]}</span>'
        )
    elif _pipeline_status["error"]:
        return HTMLResponse(f'<span class="text-danger">Error: {_pipeline_status["error"]}</span>')
    elif _pipeline_status["message"]:
        return HTMLResponse(f'<span class="text-success">{_pipeline_status["message"]}</span>')
    else:
        return HTMLResponse("<span>Ready</span>")
