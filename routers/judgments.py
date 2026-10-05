from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawJudgments
from dependencies import get_current_user, templates, require_user_permission, user_can_access_case

router = APIRouter()


@router.get("/judgments", response_class=HTMLResponse)
async def judgments_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "judgments", "view")
    try:
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not user.can_view_all_cases:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row.id for row in cases_query.with_entities(LawCases.id).all()]
        judgments = db.query(LawJudgments).filter(LawJudgments.office_id == user.office_id, LawJudgments.case_id.in_(case_ids)).order_by(LawJudgments.judgment_date.desc()).all() if case_ids else []
        cases = cases_query.all()
        return templates.TemplateResponse(request=request, name="judgments.html",
            context={"user": user, "judgments": judgments, "cases": cases, "active_page": "judgments"})
    except Exception as exc:
        return safe_error_html(exc, context="judgments.py")

@router.post("/judgments/add")
async def add_judgment(
    request: Request,
    case_id: int = Form(...),
    judgment_date: str = Form(...),
    court_name: str = Form(None),
    judge_name: str = Form(None),
    status_key: str = Form('صدر الحكم'),
    judgment_text: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "judgments", "add")
    office_id = user.office_id
    if not user_can_access_case(db, user, case_id): return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
    
    j = LawJudgments(case_id=case_id, office_id=office_id,
        judgment_date=judgment_date, court_name=court_name,
        judge_name=judge_name, status_key=status_key, judgment_text=judgment_text)
    db.add(j); db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

@router.post("/judgments/edit")
async def edit_judgment(
    request: Request,
    judgment_id: int = Form(...),
    case_id: int = Form(...),
    judgment_date: str = Form(...),
    court_name: str = Form(None),
    judge_name: str = Form(None),
    status_key: str = Form('صدر الحكم'),
    judgment_text: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "judgments", "edit")
    j = db.query(LawJudgments).filter(LawJudgments.id == judgment_id, LawJudgments.office_id == user.office_id).first()
    if not j or not user_can_access_case(db, user, j.case_id): raise HTTPException(status_code=403, detail="غير مصرح بتعديل هذا الحكم")
    if j:
        j.judgment_date = judgment_date; j.court_name = court_name
        j.judge_name = judge_name; j.status_key = status_key
        j.judgment_text = judgment_text
        db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

