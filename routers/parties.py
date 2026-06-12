from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawParties
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/parties", response_class=HTMLResponse)
async def parties_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        parties = db.query(LawParties).filter(LawParties.office_id == (user.office_id or 1)).order_by(LawParties.id.desc()).all()
        cases = db.query(LawCases).filter(LawCases.office_id == (user.office_id or 1), LawCases.is_deleted == 0).all()
        return templates.TemplateResponse(request=request, name="parties.html",
            context={"user": user, "parties": parties, "cases": cases, "active_page": "parties"})
    except Exception as exc:
        return safe_error_html(exc, context="parties.py")

@router.post("/parties/add")
async def add_party(
    request: Request,
    case_id: int = Form(...),
    name: str = Form(...),
    role_key: str = Form(...),
    id_number: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    address: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id or 1
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
    
    party = LawParties(case_id=case_id, office_id=office_id,
        name=name, role_key=role_key, id_number=id_number,
        phone=phone, email=email, address=address)
    db.add(party); db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

@router.post("/parties/edit")
async def edit_party(
    request: Request,
    party_id: int = Form(...),
    case_id: int = Form(...),
    name: str = Form(...),
    role_key: str = Form(...),
    id_number: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    address: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    party = db.query(LawParties).filter(LawParties.id == party_id, LawParties.office_id == (user.office_id or 1)).first()
    if party:
        party.name = name; party.role_key = role_key
        party.id_number = id_number; party.phone = phone
        party.email = email; party.address = address
        db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

@router.post("/parties/delete")
async def delete_party(
    request: Request,
    party_id: int = Form(...),
    case_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    party = db.query(LawParties).filter(LawParties.id == party_id, LawParties.office_id == (user.office_id or 1)).first()
    if party: db.delete(party); db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

