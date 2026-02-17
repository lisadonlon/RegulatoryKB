"""
Document management routes (add, edit).
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from regkb.config import config
from regkb.database import Database
from regkb.importer import DocumentImporter
from regkb.web.dependencies import (
    flash,
    get_db,
    get_flashed_messages,
    get_importer,
    is_htmx_request,
)

router = APIRouter(tags=["documents"])
templates = Jinja2Templates(directory="scripts/regkb/web/templates")


@router.get("/documents/add", response_class=HTMLResponse)
async def add_document_page(
    request: Request,
    db: Database = Depends(get_db),
):
    """Add document form."""
    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "add",
        "document_types": config.document_types,
        "jurisdictions": config.jurisdictions,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("document_add.html", context)


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    file: UploadFile,
    title: str = Form(...),
    document_type: str = Form(...),
    jurisdiction: str = Form(...),
    version: str = Form(None),
    source_url: str = Form(None),
    description: str = Form(None),
    importer: DocumentImporter = Depends(get_importer),
    db: Database = Depends(get_db),
):
    """Upload a PDF document."""
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Validate PDF first to give specific error
        is_valid, validation_error = importer.is_valid_pdf(tmp_path)
        if not is_valid:
            flash(request, f"Invalid PDF: {validation_error}", "error")
            return RedirectResponse("/documents/add", status_code=303)

        # Check for duplicate
        file_hash = importer.calculate_hash(tmp_path)
        if db.document_exists(file_hash):
            flash(request, "Document already exists in the knowledge base.", "warning")
            return RedirectResponse("/documents/add", status_code=303)

        metadata = {
            "title": title,
            "document_type": document_type,
            "jurisdiction": jurisdiction,
            "version": version if version else None,
            "source_url": source_url if source_url else None,
            "description": description if description else None,
        }
        doc_id = importer.import_file(tmp_path, metadata)

        if doc_id:
            flash(request, f"Document added successfully! (ID: {doc_id})", "success")
            return RedirectResponse(f"/documents/{doc_id}", status_code=303)
        else:
            flash(request, "Import failed unexpectedly. Check server logs.", "error")
            return RedirectResponse("/documents/add", status_code=303)
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/documents/url")
async def import_from_url(
    request: Request,
    url: str = Form(...),
    title: str = Form(None),
    document_type: str = Form(...),
    jurisdiction: str = Form(...),
    version: str = Form(None),
    description: str = Form(None),
    importer: DocumentImporter = Depends(get_importer),
):
    """Import document from URL."""
    metadata = {
        "title": title if title else None,
        "document_type": document_type,
        "jurisdiction": jurisdiction,
        "version": version if version else None,
        "source_url": url,
        "description": description if description else None,
    }

    doc_id = importer.import_from_url(url, metadata)

    if doc_id:
        flash(request, f"Document added successfully! (ID: {doc_id})", "success")
        return RedirectResponse(f"/documents/{doc_id}", status_code=303)
    else:
        flash(request, "Failed to download or document already exists.", "error")
        return RedirectResponse("/documents/add", status_code=303)


@router.post("/documents/folder")
async def import_from_folder(
    request: Request,
    folder_path: str = Form(...),
    recursive: bool = Form(True),
    importer: DocumentImporter = Depends(get_importer),
):
    """Batch import from folder."""
    folder = Path(folder_path)

    if not folder.exists():
        flash(request, "Folder does not exist.", "error")
        return RedirectResponse("/documents/add", status_code=303)

    if not folder.is_dir():
        flash(request, "Path is not a directory.", "error")
        return RedirectResponse("/documents/add", status_code=303)

    result = importer.import_directory(folder, recursive=recursive, progress=False)

    flash(
        request,
        f"Import complete! Imported: {result.imported}, "
        f"Duplicates: {result.duplicates}, Errors: {result.errors}",
        "success" if result.imported > 0 else "warning",
    )

    return RedirectResponse("/documents", status_code=303)


@router.post("/documents/{doc_id}/edit")
async def edit_document(
    request: Request,
    doc_id: int,
    title: str = Form(...),
    document_type: str = Form(...),
    jurisdiction: str = Form(...),
    version: str = Form(None),
    description: str = Form(None),
    db: Database = Depends(get_db),
):
    """Update document metadata."""
    updates = {
        "title": title,
        "document_type": document_type,
        "jurisdiction": jurisdiction,
        "version": version if version else None,
        "description": description if description else None,
    }

    success = db.update_document(doc_id, **updates)

    if success:
        flash(request, "Document updated successfully!", "success")
    else:
        flash(request, "Failed to update document.", "error")

    # Return partial for HTMX, redirect otherwise
    if is_htmx_request(request):
        doc = db.get_document(doc_id=doc_id)
        return templates.TemplateResponse(
            "partials/document_meta.html",
            {"request": request, "doc": doc, "flashes": get_flashed_messages(request)},
        )

    return RedirectResponse(f"/documents/{doc_id}", status_code=303)
