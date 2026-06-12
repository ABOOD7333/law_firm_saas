from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawPleadings
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/pleadings", response_class=HTMLResponse)
async def pleadings_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        pleadings = db.query(LawPleadings).filter(LawPleadings.office_id == (user.office_id or 1)).order_by(LawPleadings.id.desc()).all()
        cases = db.query(LawCases).filter(LawCases.office_id == (user.office_id or 1), LawCases.is_deleted == 0).all()
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
    office_id = user.office_id or 1
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
    
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
    p = db.query(LawPleadings).filter(LawPleadings.id == pleading_id, LawPleadings.office_id == (user.office_id or 1)).first()
    if p:
        p.title = title; p.pleading_type_key = pleading_type_key
        p.content_html = content_html; p.issue_date = issue_date
        p.status_key = status_key
        db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

