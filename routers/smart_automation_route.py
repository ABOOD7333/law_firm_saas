from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawParties, LawClients,
    LawHearings, LawTasks, LawTemplates
)
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/automation", response_class=HTMLResponse)
async def automation_page(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        _office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == _office_id).all()
        return templates.TemplateResponse(request=request, name="automation.html",
            context={"user": user, "cases": cases, "active_page": "automation"})
    except Exception as exc:
        return safe_error_html(exc, context="smart_automation_route.py")

@router.get("/api/conflict-check")
async def conflict_check(
    name: str,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"error":"unauthorized"}, status_code=401)
    office_id = user.office_id or 1
    results = []
    # Check in parties
    parties = db.query(LawParties).filter(
        LawParties.office_id == office_id,
        LawParties.name.ilike(f"%{name}%")
    ).all()
    for p in parties:
        case = db.query(LawCases).filter(LawCases.id == p.case_id, LawCases.office_id == office_id).first()
        results.append({
            "type": "طرف في قضية",
            "name": p.name,
            "role": p.role_key or "",
            "case_number": case.case_number if case else "-",
            "case_title": case.title if case else "-"
        })
    # Check in clients
    clients = db.query(LawClients).filter(
        LawClients.office_id == office_id,
        LawClients.name.ilike(f"%{name}%")
    ).all()
    for c in clients:
        case = db.query(LawCases).filter(LawCases.id == c.case_id, LawCases.office_id == office_id).first()
        results.append({
            "type": "موكل",
            "name": c.name,
            "role": "موكل",
            "case_number": case.case_number if case else "-",
            "case_title": case.title if case else "-"
        })
    return JSONResponse({"results": results, "count": len(results)})

@router.get("/api/case/{case_id}/timeline")
async def case_timeline(
    case_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"error":"unauthorized"}, status_code=401)
    office_id = user.office_id or 1
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case: return JSONResponse({"error":"not found"}, status_code=404)
    
    events = []
    # Hearings
    hearings = db.query(LawHearings).filter(LawHearings.case_id == case_id).order_by(LawHearings.hearing_at).all()
    for h in hearings:
        events.append({"date": str(h.hearing_at or "")[:10], "type": "جلسة", "title": h.title or "جلسة", "status": h.status_key or ""})
    # Tasks
    tasks = db.query(LawTasks).filter(LawTasks.case_id == case_id).order_by(LawTasks.due_at).all()
    for t in tasks:
        events.append({"date": str(t.due_at or "")[:10], "type": "مهمة", "title": t.title or "مهمة", "status": t.status_key or ""})
    events.sort(key=lambda x: x["date"] or "")
    return JSONResponse({"events": events})

@router.get("/api/templates/{template_key}")
async def get_template(
    template_key: str,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id or 1
    tmpl = db.query(LawTemplates).filter(
        LawTemplates.office_id == office_id, 
        LawTemplates.template_key == template_key
    ).first()
    
    return JSONResponse({"template_text": tmpl.template_text if tmpl else None})

@router.post("/api/templates/update")
async def update_template(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id or 1
    data = await request.json()
    template_key = data.get("template_key")
    template_text = data.get("template_text")
    
    if not template_key or not template_text:
        return JSONResponse({"error": "Missing data"}, status_code=400)
        
    tmpl = db.query(LawTemplates).filter(
        LawTemplates.office_id == office_id, 
        LawTemplates.template_key == template_key
    ).first()
    
    if tmpl:
        tmpl.template_text = template_text
    else:
        tmpl = LawTemplates(
            office_id=office_id,
            template_key=template_key,
            template_text=template_text
        )
        db.add(tmpl)
    db.commit()
    return JSONResponse({"success": True})

