"""
Browse/list routes.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from regkb.config import config
from regkb.database import Database
from regkb.web.dependencies import get_db, get_flashed_messages, is_htmx_request

router = APIRouter(tags=["browse"])
templates = Jinja2Templates(directory="scripts/regkb/web/templates")


@router.get("/documents", response_class=HTMLResponse)
async def list_documents(
    request: Request,
    type: str = "",
    jurisdiction: str = "",
    page: int = 1,
    per_page: int = 25,
    latest_only: bool = True,
    db: Database = Depends(get_db),
):
    """List documents with filtering and pagination."""
    offset = (page - 1) * per_page

    documents = db.list_documents(
        document_type=type if type else None,
        jurisdiction=jurisdiction if jurisdiction else None,
        latest_only=latest_only,
        limit=per_page,
        offset=offset,
    )

    # Get total count for pagination (approximate)
    stats = db.get_statistics()
    total = stats["total_documents"]

    total_pages = (total + per_page - 1) // per_page

    context = {
        "request": request,
        "active_page": "browse",
        "documents": documents,
        "selected_type": type,
        "selected_jurisdiction": jurisdiction,
        "page": page,
        "per_page": per_page,
        "latest_only": latest_only,
        "total_pages": total_pages,
        "document_types": config.document_types,
        "jurisdictions": config.jurisdictions,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    # Return partial for HTMX requests
    if is_htmx_request(request):
        return templates.TemplateResponse("partials/document_list.html", context)

    return templates.TemplateResponse("browse.html", context)


@router.get("/documents/{doc_id}", response_class=HTMLResponse)
async def document_detail(
    request: Request,
    doc_id: int,
    db: Database = Depends(get_db),
):
    """View single document details."""
    doc = db.get_document(doc_id=doc_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Read extracted text if available
    extracted_text = ""
    if doc.get("extracted_path"):
        extracted_path = Path(doc["extracted_path"])
        if extracted_path.exists():
            extracted_text = extracted_path.read_text(encoding="utf-8")

    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "browse",
        "doc": doc,
        "extracted_text": extracted_text,
        "document_types": config.document_types,
        "jurisdictions": config.jurisdictions,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("document_detail.html", context)


@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: int,
    db: Database = Depends(get_db),
):
    """Download document PDF."""
    doc = db.get_document(doc_id=doc_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/pdf",
    )


@router.get("/documents/{doc_id}/text", response_class=PlainTextResponse)
async def document_text(
    doc_id: int,
    db: Database = Depends(get_db),
):
    """Get extracted text for a document."""
    doc = db.get_document(doc_id=doc_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.get("extracted_path"):
        raise HTTPException(status_code=404, detail="No extracted text available")

    extracted_path = Path(doc["extracted_path"])
    if not extracted_path.exists():
        raise HTTPException(status_code=404, detail="Extracted text file not found")

    return extracted_path.read_text(encoding="utf-8")
