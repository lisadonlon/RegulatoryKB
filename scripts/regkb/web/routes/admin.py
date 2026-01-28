"""
Admin routes (stats, settings, backup, reindex).
"""

import threading

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from regkb.config import config
from regkb.database import Database
from regkb.search import SearchEngine
from regkb.web.dependencies import flash, get_db, get_flashed_messages, get_search_engine

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="scripts/regkb/web/templates")

# Reindex status tracking
reindex_status = {"running": False, "progress": 0, "total": 0, "error": None}
reindex_lock = threading.Lock()


def do_reindex(search_engine: SearchEngine):
    """Background reindex task."""
    global reindex_status
    with reindex_lock:
        reindex_status = {"running": True, "progress": 0, "total": 0, "error": None}

    def progress_callback(done, total):
        reindex_status["progress"] = done
        reindex_status["total"] = total

    try:
        count = search_engine.reindex_all(progress_callback=progress_callback)
        reindex_status["running"] = False
        reindex_status["progress"] = count
        reindex_status["total"] = count
    except Exception as e:
        reindex_status["error"] = str(e)
        reindex_status["running"] = False


@router.get("/stats", response_class=HTMLResponse)
async def statistics_page(
    request: Request,
    db: Database = Depends(get_db),
):
    """Statistics dashboard."""
    stats = db.get_statistics()

    # Prepare chart data
    by_type = stats.get("by_type", {})
    by_jurisdiction = stats.get("by_jurisdiction", {})

    context = {
        "request": request,
        "active_page": "stats",
        "stats": stats,
        "by_type": by_type,
        "by_jurisdiction": by_jurisdiction,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("statistics.html", context)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: Database = Depends(get_db),
):
    """Settings and admin actions."""
    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "settings",
        "stats": stats,
        "config": config,
        "reindex_status": reindex_status,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("settings.html", context)


@router.post("/backup")
async def create_backup(
    request: Request,
    db: Database = Depends(get_db),
):
    """Create database backup."""
    try:
        backup_path = db.backup()
        flash(request, f"Backup created: {backup_path}", "success")
    except Exception as e:
        flash(request, f"Backup failed: {e}", "error")

    return RedirectResponse("/admin/settings", status_code=303)


@router.post("/reindex")
async def start_reindex(
    request: Request,
    background_tasks: BackgroundTasks,
    search_engine: SearchEngine = Depends(get_search_engine),
):
    """Start reindex in background."""
    if reindex_status["running"]:
        flash(request, "Reindex already in progress.", "warning")
    else:
        background_tasks.add_task(do_reindex, search_engine)
        flash(request, "Reindex started. Refresh to check status.", "info")

    return RedirectResponse("/admin/settings", status_code=303)


@router.get("/reindex/status")
async def get_reindex_status():
    """Get reindex progress (for polling)."""
    return JSONResponse(reindex_status)
