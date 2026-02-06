"""
Document version checking routes.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from regkb.database import Database
from regkb.version_tracker import check_all_versions, get_version_summary
from regkb.web.dependencies import get_db, get_flashed_messages

router = APIRouter(tags=["versions"])
templates = Jinja2Templates(directory="scripts/regkb/web/templates")


@router.get("/versions", response_class=HTMLResponse)
async def versions_page(
    request: Request,
    db: Database = Depends(get_db),
):
    """Check and display version status for all documents."""
    # Get database path from the db instance
    db_path = str(db.db_path)

    # Run version check
    results = check_all_versions(db_path)
    summary = get_version_summary(results)

    # Group results by status
    outdated = [r for r in results if r.status == "outdated"]
    current = [r for r in results if r.status == "current"]
    unknown = [r for r in results if r.status == "unknown"]

    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "versions",
        "summary": summary,
        "outdated": outdated,
        "current": current,
        "unknown": unknown,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("versions.html", context)
