"""
Search routes.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from regkb.config import config
from regkb.database import Database
from regkb.search import SearchEngine
from regkb.web.dependencies import (
    get_db,
    get_flashed_messages,
    get_search_engine,
    is_htmx_request,
)

router = APIRouter(tags=["search"])
templates = Jinja2Templates(directory="scripts/regkb/web/templates")


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = "",
    type: str = "",
    jurisdiction: str = "",
    limit: int = 10,
    db: Database = Depends(get_db),
    search_engine: SearchEngine = Depends(get_search_engine),
):
    """Search page with optional query parameters."""
    results = []
    searched = False

    if q:
        searched = True
        results = search_engine.search(
            query=q,
            limit=limit,
            document_type=type if type else None,
            jurisdiction=jurisdiction if jurisdiction else None,
            include_excerpt=True,
        )

    # Get recent documents if no search
    recent = []
    if not searched:
        recent = db.list_documents(limit=5)

    # Get stats for footer
    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "search",
        "query": q,
        "selected_type": type,
        "selected_jurisdiction": jurisdiction,
        "limit": limit,
        "results": results,
        "searched": searched,
        "recent": recent,
        "document_types": config.document_types,
        "jurisdictions": config.jurisdictions,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    # Return partial for HTMX requests
    if is_htmx_request(request) and searched:
        return templates.TemplateResponse("partials/search_results.html", context)

    return templates.TemplateResponse("search.html", context)


@router.post("/search", response_class=HTMLResponse)
async def search_submit(
    request: Request,
    db: Database = Depends(get_db),
    search_engine: SearchEngine = Depends(get_search_engine),
):
    """Handle search form submission."""
    form = await request.form()
    q = form.get("q", "")
    type_filter = form.get("type", "")
    jurisdiction_filter = form.get("jurisdiction", "")
    limit = int(form.get("limit", 10))

    results = []
    if q:
        results = search_engine.search(
            query=q,
            limit=limit,
            document_type=type_filter if type_filter else None,
            jurisdiction=jurisdiction_filter if jurisdiction_filter else None,
            include_excerpt=True,
        )

    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "search",
        "query": q,
        "selected_type": type_filter,
        "selected_jurisdiction": jurisdiction_filter,
        "limit": limit,
        "results": results,
        "searched": True,
        "recent": [],
        "document_types": config.document_types,
        "jurisdictions": config.jurisdictions,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    # Return partial for HTMX requests
    if is_htmx_request(request):
        return templates.TemplateResponse("partials/search_results.html", context)

    return templates.TemplateResponse("search.html", context)
