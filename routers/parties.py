from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawParties
from dependencies import get_current_user, templates, require_user_permission, user_can_access_case

router = APIRouter()


@router.get("/parties", response_class=HTMLResponse)
async def parties_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "parties", "view")
    try:
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not user.can_view_all_cases:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row.id for row in cases_query.with_entities(LawCases.id).all()]
        parties = db.query(LawParties).filter(LawParties.office_id == user.office_id, LawParties.case_id.in_(case_ids)).order_by(LawParties.id.desc()).all() if case_ids else []
        cases = cases_query.all()
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
    require_user_permission(user, "parties", "add")
    office_id = user.office_id
    if not user_can_access_case(db, user, case_id): raise HTTPException(status_code=403, detail="غير مصرح بهذه القضية")
    
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
    require_user_permission(user, "parties", "edit")
    party = db.query(LawParties).filter(LawParties.id == party_id, LawParties.office_id == user.office_id).first()
    if not party or not user_can_access_case(db, user, party.case_id): raise HTTPException(status_code=403, detail="غير مصرح بتعديل هذا السجل")
    if not user_can_access_case(db, user, case_id): raise HTTPException(status_code=403, detail="غير مصرح بهذه القضية")
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
    require_user_permission(user, "parties", "delete")
    party = db.query(LawParties).filter(LawParties.id == party_id, LawParties.office_id == user.office_id).first()
    if not party or not user_can_access_case(db, user, party.case_id): raise HTTPException(status_code=403, detail="غير مصرح بحذف هذا السجل")
    if party: db.delete(party); db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

