"""
Document comparison routes.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from regkb.database import Database
from regkb.diff import compare_documents
from regkb.web.dependencies import get_db, get_flashed_messages

router = APIRouter(tags=["diff"])
templates = Jinja2Templates(directory="scripts/regkb/web/templates")


@router.get("/diff", response_class=HTMLResponse)
async def diff_page(
    request: Request,
    doc1: int = 0,
    doc2: int = 0,
    db: Database = Depends(get_db),
):
    """Document comparison page with selectors."""
    documents = db.list_documents(latest_only=False, limit=1000, offset=0)
    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "diff",
        "documents": documents,
        "selected_doc1": doc1,
        "selected_doc2": doc2,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("diff.html", context)


@router.get("/diff/result", response_class=HTMLResponse)
async def diff_result(
    request: Request,
    doc1: int = 0,
    doc2: int = 0,
    context_lines: int = 3,
    db: Database = Depends(get_db),
):
    """Run comparison and return results (HTMX partial)."""
    if not doc1 or not doc2:
        return HTMLResponse("<p>Please select two documents to compare.</p>")

    if doc1 == doc2:
        return HTMLResponse("<p>Please select two <em>different</em> documents.</p>")

    doc1_info = db.get_document(doc_id=doc1)
    doc2_info = db.get_document(doc_id=doc2)

    if not doc1_info:
        return HTMLResponse(f"<p>Document {doc1} not found.</p>")
    if not doc2_info:
        return HTMLResponse(f"<p>Document {doc2} not found.</p>")

    result = compare_documents(
        doc1_id=doc1,
        doc2_id=doc2,
        doc1_title=doc1_info["title"],
        doc2_title=doc2_info["title"],
        context_lines=context_lines,
        include_html=True,
    )

    if result is None:
        missing = []
        if not doc1_info.get("extracted_path"):
            missing.append(f"#{doc1} ({doc1_info['title']})")
        if not doc2_info.get("extracted_path"):
            missing.append(f"#{doc2} ({doc2_info['title']})")
        msg = (
            "Missing extracted text for: " + ", ".join(missing)
            if missing
            else ("Could not read extracted text files. Try re-extracting with the CLI.")
        )
        return HTMLResponse(f'<article class="flash flash-error">{msg}</article>')

    stats = result.stats
    context = {
        "request": request,
        "result": result,
        "stats": stats,
    }

    return templates.TemplateResponse("partials/diff_result.html", context)
