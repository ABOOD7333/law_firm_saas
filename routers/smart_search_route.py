from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawClients, LawParties,
    LawHearings, LawPleadings, LawJudgments, LawNotes
)
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = "",
    scope: str = "all",
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    results = {"cases": [], "clients": [], "parties": [], "hearings": [], "pleadings": [], "judgments": [], "notes": []}
    if q and q.strip():
        term = q.strip()
        like = f"%{term}%"
        office_id = user.office_id or 1
        if scope in ("all", "cases"):
            results["cases"] = db.query(LawCases).filter(
                LawCases.office_id == office_id,
                (LawCases.title.ilike(like)) |
                (LawCases.case_number.ilike(like)) |
                (LawCases.summary.ilike(like)) |
                (LawCases.description.ilike(like))
            ).limit(15).all()
        if scope in ("all", "clients"):
            results["clients"] = db.query(LawClients).filter(
                LawClients.office_id == office_id,
                (LawClients.name.ilike(like)) |
                (LawClients.phone.ilike(like)) |
                (LawClients.national_id.ilike(like))
            ).limit(15).all()
        if scope in ("all", "parties"):
            results["parties"] = db.query(LawParties).filter(
                LawParties.office_id == office_id,
                (LawParties.name.ilike(like)) |
                (LawParties.phone.ilike(like)) |
                (LawParties.id_number.ilike(like))
            ).limit(15).all()
        if scope in ("all", "hearings"):
            results["hearings"] = db.query(LawHearings).filter(
                LawHearings.office_id == office_id,
                (LawHearings.title.ilike(like)) |
                (LawHearings.result_summary.ilike(like))
            ).limit(15).all()
        if scope in ("all", "pleadings"):
            results["pleadings"] = db.query(LawPleadings).filter(
                LawPleadings.office_id == office_id,
                (LawPleadings.title.ilike(like)) |
                (LawPleadings.content_html.ilike(like))
            ).limit(15).all()
        if scope in ("all", "judgments"):
            results["judgments"] = db.query(LawJudgments).filter(
                LawJudgments.office_id == office_id,
                (LawJudgments.court_name.ilike(like)) |
                (LawJudgments.judge_name.ilike(like)) |
                (LawJudgments.judgment_text.ilike(like)) |
                (LawJudgments.status_key.ilike(like))
            ).limit(15).all()
        if scope in ("all", "notes"):
            results["notes"] = db.query(LawNotes).filter(
                LawNotes.office_id == office_id,
                (LawNotes.title.ilike(like)) |
                (LawNotes.content.ilike(like))
            ).limit(15).all()
    total = sum(len(v) for v in results.values())
    return templates.TemplateResponse(request=request, name="search.html",
        context={"user": user, "q": q, "scope": scope, "results": results,
                 "total": total, "active_page": "search"})

