"""
Admin routes (stats, settings, backup, reindex).
"""

import threading

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from regkb.config import config
from regkb.database import Database
from regkb.extraction import TextExtractor
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


# Batch operation status
batch_status = {"running": False, "operation": "", "progress": 0, "total": 0, "error": None}


def do_batch_reextract(doc_ids: list[int], db: Database, force_ocr: bool = False):
    """Background task: re-extract text for selected documents."""
    global batch_status
    batch_status = {
        "running": True,
        "operation": "Re-extracting",
        "progress": 0,
        "total": len(doc_ids),
        "error": None,
    }

    extractor = TextExtractor()
    success = 0

    for i, doc_id in enumerate(doc_ids):
        try:
            doc = db.get_document(doc_id=doc_id)
            if doc and doc.get("file_path"):
                from pathlib import Path

                pdf_path = Path(doc["file_path"])
                if pdf_path.exists():
                    ok, extracted_path, text = extractor.re_extract(pdf_path, doc_id, force_ocr)
                    if ok and extracted_path:
                        db.update_document(
                            doc_id, extracted_path=str(extracted_path), extracted_text=text
                        )
                        success += 1
        except Exception:
            pass
        batch_status["progress"] = i + 1

    batch_status["running"] = False
    batch_status["operation"] = f"Re-extracted {success}/{len(doc_ids)} documents"


def do_batch_update_metadata(doc_ids: list[int], db: Database, doc_type: str, jurisdiction: str):
    """Background task: update metadata for selected documents."""
    global batch_status
    batch_status = {
        "running": True,
        "operation": "Updating metadata",
        "progress": 0,
        "total": len(doc_ids),
        "error": None,
    }

    success = 0
    updates = {}
    if doc_type:
        updates["document_type"] = doc_type
    if jurisdiction:
        updates["jurisdiction"] = jurisdiction

    for i, doc_id in enumerate(doc_ids):
        try:
            if updates:
                db.update_document(doc_id, **updates)
                success += 1
        except Exception:
            pass
        batch_status["progress"] = i + 1

    batch_status["running"] = False
    batch_status["operation"] = f"Updated {success}/{len(doc_ids)} documents"


@router.get("/batch", response_class=HTMLResponse)
async def batch_page(
    request: Request,
    type: str = "",
    jurisdiction: str = "",
    db: Database = Depends(get_db),
):
    """Batch operations page."""
    documents = db.list_documents(
        document_type=type if type else None,
        jurisdiction=jurisdiction if jurisdiction else None,
        latest_only=False,
        limit=500,
    )
    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "settings",
        "documents": documents,
        "selected_type": type,
        "selected_jurisdiction": jurisdiction,
        "document_types": config.document_types,
        "jurisdictions": config.jurisdictions,
        "batch_status": batch_status,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("admin_batch.html", context)


@router.post("/batch/reextract")
async def batch_reextract(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
):
    """Re-extract text for selected documents."""
    global batch_status

    if batch_status["running"]:
        flash(request, "Batch operation already in progress", "warning")
        return RedirectResponse("/admin/batch", status_code=303)

    form = await request.form()
    doc_ids = [int(id) for id in form.getlist("doc_ids")]
    force_ocr = form.get("force_ocr") == "on"

    if not doc_ids:
        flash(request, "No documents selected", "warning")
    else:
        background_tasks.add_task(do_batch_reextract, doc_ids, db, force_ocr)
        flash(request, f"Re-extracting {len(doc_ids)} documents in background", "info")

    return RedirectResponse("/admin/batch", status_code=303)


@router.post("/batch/update-metadata")
async def batch_update_metadata(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
):
    """Update metadata for selected documents."""
    global batch_status

    if batch_status["running"]:
        flash(request, "Batch operation already in progress", "warning")
        return RedirectResponse("/admin/batch", status_code=303)

    form = await request.form()
    doc_ids = [int(id) for id in form.getlist("doc_ids")]
    new_type = form.get("new_type", "")
    new_jurisdiction = form.get("new_jurisdiction", "")

    if not doc_ids:
        flash(request, "No documents selected", "warning")
    elif not new_type and not new_jurisdiction:
        flash(request, "No changes specified", "warning")
    else:
        background_tasks.add_task(do_batch_update_metadata, doc_ids, db, new_type, new_jurisdiction)
        flash(request, f"Updating {len(doc_ids)} documents in background", "info")

    return RedirectResponse("/admin/batch", status_code=303)


@router.get("/batch/status")
async def get_batch_status():
    """Get batch operation progress."""
    return JSONResponse(batch_status)
