from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawCorrespondences, LawClients, LawParties
from dependencies import get_current_user, templates

router = APIRouter()


from database.models import LawCorrespondences

@router.get("/correspondences", response_class=HTMLResponse)
async def correspondences_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        office_id = user.office_id or 1
        corrs = db.query(LawCorrespondences).filter(LawCorrespondences.office_id == office_id).order_by(LawCorrespondences.id.desc()).all()
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
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
    office_id = user.office_id or 1
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
    
    response_status = "بانتظار الرد" if needs_reply == "نعم" else "لا يتطلب رد"
    c = LawCorrespondences(
        case_id=case_id, office_id=user.office_id or 1,
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
    c = db.query(LawCorrespondences).filter(LawCorrespondences.id == corr_id, LawCorrespondences.office_id == (user.office_id or 1)).first()
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
    c = db.query(LawCorrespondences).filter(LawCorrespondences.id == corr_id, LawCorrespondences.office_id == (user.office_id or 1)).first()
    if c: db.delete(c); db.commit()
    return RedirectResponse(url="/correspondences", status_code=303)

