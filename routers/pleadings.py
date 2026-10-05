from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawPleadings
from dependencies import get_current_user, templates, require_user_permission, user_can_access_case

router = APIRouter()


@router.get("/pleadings", response_class=HTMLResponse)
async def pleadings_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "pleadings", "view")
    try:
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not user.can_view_all_cases:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row.id for row in cases_query.with_entities(LawCases.id).all()]
        pleadings = db.query(LawPleadings).filter(LawPleadings.office_id == user.office_id, LawPleadings.case_id.in_(case_ids)).order_by(LawPleadings.id.desc()).all() if case_ids else []
        cases = cases_query.all()
        return templates.TemplateResponse(request=request, name="pleadings.html",
            context={"user": user, "pleadings": pleadings, "cases": cases, "active_page": "pleadings"})
    except Exception as exc:
        return safe_error_html(exc, context="pleadings.py")

@router.post("/pleadings/add")
async def add_pleading(
    request: Request,
    case_id: int = Form(...),
    title: str = Form(...),
    pleading_type_key: str = Form(...),
    content_html: str = Form(None),
    issue_date: str = Form(None),
    status_key: str = Form('draft'),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "pleadings", "add")
    office_id = user.office_id
    if not user_can_access_case(db, user, case_id): return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
    
    pleading = LawPleadings(case_id=case_id, office_id=office_id,
        title=title, pleading_type_key=pleading_type_key,
        content_html=content_html, issue_date=issue_date,
        status_key=status_key, lead_lawyer_id=user.id)
    db.add(pleading); db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

@router.post("/pleadings/edit")
async def edit_pleading(
    request: Request,
    pleading_id: int = Form(...),
    case_id: int = Form(...),
    title: str = Form(...),
    pleading_type_key: str = Form(...),
    content_html: str = Form(None),
    issue_date: str = Form(None),
    status_key: str = Form('draft'),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "pleadings", "edit")
    p = db.query(LawPleadings).filter(LawPleadings.id == pleading_id, LawPleadings.office_id == user.office_id).first()
    if not p or not user_can_access_case(db, user, p.case_id): raise HTTPException(status_code=403, detail="غير مصرح بتعديل هذه المذكرة")
    if p:
        p.title = title; p.pleading_type_key = pleading_type_key
        p.content_html = content_html; p.issue_date = issue_date
        p.status_key = status_key
        db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

