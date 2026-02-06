"""
Intelligence pipeline management routes.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from regkb.database import Database
from regkb.intelligence.analyzer import KBAnalyzer
from regkb.intelligence.digest_tracker import DigestTracker
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
        result = fetcher.fetch_all(days_back=7)

        _pipeline_status["message"] = (
            f"Fetched {result.total_entries} entries from {result.sources_fetched} sources"
        )
    except Exception as e:
        _pipeline_status["error"] = str(e)
    finally:
        _pipeline_status["running"] = False


def run_sync_task(db_path: str):
    """Background task: full sync (fetch, filter, analyze)."""
    global _pipeline_status
    try:
        _pipeline_status["stage"] = "Fetching"
        _pipeline_status["message"] = "Fetching newsletter entries..."

        fetcher = NewsletterFetcher()
        fetch_result = fetcher.fetch_all(days_back=7)

        _pipeline_status["stage"] = "Filtering"
        _pipeline_status["message"] = f"Filtering {fetch_result.total_entries} entries..."

        content_filter = ContentFilter()
        filter_result = content_filter.filter_entries(fetch_result.entries)

        _pipeline_status["stage"] = "Analyzing"
        _pipeline_status["message"] = f"Analyzing {len(filter_result.entries)} relevant entries..."

        analyzer = KBAnalyzer(db_path=db_path)
        analysis = analyzer.analyze(filter_result)

        _pipeline_status["message"] = str(analysis)
    except Exception as e:
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
    db: Database = Depends(get_db),
):
    """Run full sync (fetch, filter, analyze)."""
    global _pipeline_status

    if _pipeline_status["running"]:
        flash(request, "Pipeline already running", "warning")
    else:
        _pipeline_status = {"running": True, "stage": "", "message": "", "error": None}
        background_tasks.add_task(run_sync_task, str(db.db_path))
        flash(request, "Sync started in background", "info")

    return RedirectResponse(url="/intel", status_code=303)


@router.get("/intel/status", response_class=HTMLResponse)
async def intel_status(request: Request):
    """Get current pipeline status (HTMX partial)."""
    global _pipeline_status

    if _pipeline_status["error"]:
        return HTMLResponse(f'<span class="text-danger">Error: {_pipeline_status["error"]}</span>')
    elif _pipeline_status["running"]:
        return HTMLResponse(
            f'<span aria-busy="true">{_pipeline_status["stage"]}: {_pipeline_status["message"]}</span>'
        )
    elif _pipeline_status["message"]:
        return HTMLResponse(f'<span class="text-success">{_pipeline_status["message"]}</span>')
    else:
        return HTMLResponse("<span>Ready</span>")
