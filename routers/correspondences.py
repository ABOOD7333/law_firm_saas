from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawCorrespondences, LawClients, LawParties
from dependencies import get_current_user, templates, require_user_permission, user_can_access_case

router = APIRouter()


from database.models import LawCorrespondences

@router.get("/correspondences", response_class=HTMLResponse)
async def correspondences_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "correspondences", "view")
    try:
        office_id = user.office_id
        cases_query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not user.can_view_all_cases:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row.id for row in cases_query.with_entities(LawCases.id).all()]
        corrs = db.query(LawCorrespondences).filter(LawCorrespondences.office_id == office_id, LawCorrespondences.case_id.in_(case_ids)).order_by(LawCorrespondences.id.desc()).all() if case_ids else []
        cases = cases_query.all()
        return templates.TemplateResponse(request=request, name="correspondences.html",
            context={"user": user, "corrs": corrs, "cases": cases, "active_page": "correspondences"})
    except Exception as exc:
        return safe_error_html(exc, context="correspondences.py")

@router.post("/correspondences/add")
async def add_correspondence(
    request: Request,
    case_id: int = Form(...),
    direction_key: str = Form(...),
    letter_number: str = Form(None),
    letter_date: str = Form(None),
    subject: str = Form(None),
    needs_reply: str = Form(None),
    reply_due_date: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "correspondences", "add")
    office_id = user.office_id
    if not user_can_access_case(db, user, case_id): return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
    
    response_status = "بانتظار الرد" if needs_reply == "نعم" else "لا يتطلب رد"
    c = LawCorrespondences(
        case_id=case_id, office_id=office_id,
        direction_key=direction_key, letter_number=letter_number,
        letter_date=letter_date, subject=subject,
        needs_reply=needs_reply, reply_due_date=reply_due_date,
        response_status=response_status
    )
    db.add(c); db.commit()
    return RedirectResponse(url="/correspondences", status_code=303)

@router.post("/correspondences/edit")
async def edit_correspondence(
    request: Request,
    corr_id: int = Form(...),
    direction_key: str = Form(...),
    letter_number: str = Form(None),
    letter_date: str = Form(None),
    subject: str = Form(None),
    needs_reply: str = Form(None),
    reply_due_date: str = Form(None),
    response_status: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "correspondences", "edit")
    c = db.query(LawCorrespondences).filter(LawCorrespondences.id == corr_id, LawCorrespondences.office_id == user.office_id).first()
    if not c or not user_can_access_case(db, user, c.case_id): raise HTTPException(status_code=403, detail="غير مصرح بتعديل هذه المراسلة")
    if c:
        c.direction_key = direction_key; c.letter_number = letter_number
        c.letter_date = letter_date; c.subject = subject
        c.needs_reply = needs_reply; c.reply_due_date = reply_due_date
        c.response_status = response_status
        db.commit()
    return RedirectResponse(url="/correspondences", status_code=303)

@router.post("/correspondences/delete")
async def delete_correspondence(
    request: Request,
    corr_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "correspondences", "delete")
    c = db.query(LawCorrespondences).filter(LawCorrespondences.id == corr_id, LawCorrespondences.office_id == user.office_id).first()
    if not c or not user_can_access_case(db, user, c.case_id): raise HTTPException(status_code=403, detail="غير مصرح بحذف هذه المراسلة")
    if c: db.delete(c); db.commit()
    return RedirectResponse(url="/correspondences", status_code=303)

