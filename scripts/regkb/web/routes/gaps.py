"""
Gap analysis routes.
"""

import csv
import io

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from regkb.database import Database
from regkb.gap_analysis import get_gap_summary, run_gap_analysis
from regkb.web.dependencies import get_db, get_flashed_messages

router = APIRouter(tags=["gaps"])
templates = Jinja2Templates(directory="scripts/regkb/web/templates")


@router.get("/gaps", response_class=HTMLResponse)
async def gaps_page(
    request: Request,
    mandatory_only: bool = False,
    db: Database = Depends(get_db),
):
    """Gap analysis dashboard showing coverage against reference checklist."""
    db_path = str(db.db_path)

    # Run gap analysis
    results = run_gap_analysis(db_path)
    summary = get_gap_summary(results)

    # Priority order for display, then any remaining jurisdictions
    priority_order = ["EU", "FDA", "UK", "Health Canada", "TGA", "ISO", "ICH", "IMDRF"]
    jurisdictions = []
    seen = set()
    for jur in priority_order:
        if jur in summary["by_jurisdiction"]:
            jurisdictions.append({"name": jur, **summary["by_jurisdiction"][jur]})
            seen.add(jur)
    for jur in sorted(summary["by_jurisdiction"]):
        if jur not in seen:
            jurisdictions.append({"name": jur, **summary["by_jurisdiction"][jur]})

    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "gaps",
        "summary": summary,
        "jurisdictions": jurisdictions,
        "mandatory_only": mandatory_only,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("gaps.html", context)


@router.get("/gaps/{jurisdiction}", response_class=HTMLResponse)
async def gaps_jurisdiction(
    request: Request,
    jurisdiction: str,
    db: Database = Depends(get_db),
):
    """Drill-down view for a specific jurisdiction's gap analysis."""
    db_path = str(db.db_path)

    results = run_gap_analysis(db_path)

    if jurisdiction not in results:
        return HTMLResponse(f"<p>Jurisdiction '{jurisdiction}' not found.</p>", status_code=404)

    matches = results[jurisdiction]
    summary = get_gap_summary(results)
    jur_stats = summary["by_jurisdiction"][jurisdiction]

    # Group by category
    by_category = {}
    for match in matches:
        cat = match.category
        if cat not in by_category:
            by_category[cat] = {"matched": [], "missing": []}
        if match.matched:
            by_category[cat]["matched"].append(match)
        else:
            by_category[cat]["missing"].append(match)

    # Sort missing: mandatory first
    for cat in by_category:
        by_category[cat]["missing"].sort(key=lambda m: (not m.mandatory, m.ref_title))

    stats = db.get_statistics()

    context = {
        "request": request,
        "active_page": "gaps",
        "jurisdiction": jurisdiction,
        "jur_stats": jur_stats,
        "by_category": by_category,
        "stats": stats,
        "flashes": get_flashed_messages(request),
    }

    return templates.TemplateResponse("gaps_detail.html", context)


@router.get("/gaps/export/csv")
async def gaps_export(
    db: Database = Depends(get_db),
):
    """Export full gap analysis to CSV."""
    db_path = str(db.db_path)
    results = run_gap_analysis(db_path)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Jurisdiction",
            "Category",
            "Ref ID",
            "Title",
            "Description",
            "Mandatory",
            "Status",
            "KB Doc ID",
            "KB Doc Title",
            "Confidence",
        ]
    )

    for jurisdiction, matches in results.items():
        for m in matches:
            writer.writerow(
                [
                    jurisdiction,
                    m.category,
                    m.ref_id,
                    m.ref_title,
                    m.ref_description,
                    "Yes" if m.mandatory else "No",
                    "Matched" if m.matched else "Missing",
                    m.kb_doc_id or "",
                    m.kb_doc_title or "",
                    f"{m.match_confidence:.2f}" if m.matched else "",
                ]
            )

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gap_analysis.csv"'},
    )
