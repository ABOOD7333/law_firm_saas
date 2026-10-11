# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
import traceback
import html
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawParties, LawClients, LawAuditLog
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter()


def log_party_audit(db: Session, office_id: int, user: AccessProfiles, action_name: str, party: LawParties, details: str = ""):
    """Security Audit Trail logger for Party operations"""
    try:
        audit = LawAuditLog(
            table_name="law_parties",
            action_name=action_name,
            record_key=str(party.id),
            actor_name=getattr(user, "name", "") or getattr(user, "username", "مستخدم"),
            actor_user_id=user.id,
            office_id=office_id,
            details=f"طرف قضائي: {party.name} (الصفة: {party.role_key} - {party.legal_capacity or ''}) | {details}"
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        print(f"[Audit Log Error] {e}")


def sanitize_input(value: str, max_length: int = 255) -> str:
    """Clean and sanitize string input to protect against XSS and control characters"""
    if not value:
        return None
    cleaned = value.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


@router.get("/parties", response_class=HTMLResponse)
async def parties_page(
    request: Request,
    q: str = None,
    role: str = None,
    capacity: str = None,
    case_id: int = None,
    party_type: str = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        office_id = user.office_id
        if not office_id:
            raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")

        parties_query = db.query(LawParties).filter(
            LawParties.office_id == office_id,
            LawParties.is_deleted == 0
        )
        cases_query = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        )

        # RBAC: Restrict lawyer to their assigned cases if not permitted to view all
        if user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0:
            accessible_case_ids = db.query(LawCases.id).filter(
                LawCases.office_id == office_id,
                LawCases.lead_lawyer_id == user.id,
                LawCases.is_deleted == 0
            ).subquery()
            parties_query = parties_query.filter(LawParties.case_id.in_(accessible_case_ids))
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)

        # Search Query (Arabic & Multi-field)
        if q and q.strip():
            term = f"%{q.strip()}%"
            parties_query = parties_query.filter(
                or_(
                    LawParties.name.ilike(term),
                    LawParties.id_number.ilike(term),
                    LawParties.cr_number.ilike(term),
                    LawParties.phone.ilike(term),
                    LawParties.lawyer_name.ilike(term),
                    LawParties.email.ilike(term),
                    LawParties.city.ilike(term)
                )
            )

        # Filters
        if role and role.strip():
            parties_query = parties_query.filter(LawParties.role_key == role.strip())
        if capacity and capacity.strip():
            parties_query = parties_query.filter(LawParties.legal_capacity == capacity.strip())
        if party_type and party_type.strip():
            parties_query = parties_query.filter(LawParties.party_type == party_type.strip())
        if case_id:
            parties_query = parties_query.filter(LawParties.case_id == case_id)

        parties = parties_query.order_by(desc(LawParties.id)).all()
        cases = cases_query.order_by(LawCases.case_number.asc()).all()

        # Stats Counters
        total_parties = db.query(LawParties).filter(LawParties.office_id == office_id, LawParties.is_deleted == 0).count()
        total_clients = db.query(LawParties).filter(LawParties.office_id == office_id, LawParties.role_key == 'موكل', LawParties.is_deleted == 0).count()
        total_opponents = db.query(LawParties).filter(LawParties.office_id == office_id, LawParties.role_key == 'خصم', LawParties.is_deleted == 0).count()
        total_corporates = db.query(LawParties).filter(LawParties.office_id == office_id, LawParties.party_type == 'corporate', LawParties.is_deleted == 0).count()

        return templates.TemplateResponse(
            request=request,
            name="parties.html",
            context={
                "user": user,
                "parties": parties,
                "cases": cases,
                "total_parties": total_parties,
                "total_clients": total_clients,
                "total_opponents": total_opponents,
                "total_corporates": total_corporates,
                "filters": {
                    "q": q or "",
                    "role": role or "",
                    "capacity": capacity or "",
                    "party_type": party_type or "",
                    "case_id": case_id or ""
                },
                "active_page": "parties"
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="parties.py")


@router.post("/parties/add")
async def add_party(
    request: Request,
    case_id: int = Form(...),
    name: str = Form(...),
    role_key: str = Form(...),
    party_type: str = Form("individual"),
    nationality: str = Form(None),
    id_number: str = Form(None),
    cr_number: str = Form(None),
    legal_capacity: str = Form(None),
    representation_status: str = Form(None),
    phone: str = Form(None),
    alt_phone: str = Form(None),
    email: str = Form(None),
    city: str = Form(None),
    address: str = Form(None),
    national_address: str = Form(None),
    service_method: str = Form(None),
    lawyer_name: str = Form(None),
    lawyer_phone: str = Form(None),
    lawyer_license_no: str = Form(None),
    poa_number: str = Form(None),
    poa_date: str = Form(None),
    conflict_status: str = Form("clear"),
    internal_notes: str = Form(None),
    redirect_to: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    if not office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")

    # Permission check
    if not check_user_permission(user, 'cases', 'edit') and not check_user_permission(user, 'cases', 'add'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة أطراف للقضايا")

    # IDOR Check: Ensure case belongs to the tenant's office
    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="القضية غير موجودة أو غير مصرح بالوصول إليها")

    # RBAC Check: Ensure assigned lawyer if restricted
    if user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0 and case.lead_lawyer_id != user.id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة أطراف لهذه القضية")

    # Input sanitization
    safe_name = sanitize_input(name, 200)
    if not safe_name:
        raise HTTPException(status_code=400, detail="اسم الطرف مطلوب")

    # Automated Conflict of Interest Detection:
    # Check if this opponent's name or ID exists as a client in the office
    final_conflict_status = conflict_status or "clear"
    if role_key == "خصم":
        existing_client = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.name.ilike(f"%{safe_name}%")
        ).first()
        if existing_client:
            final_conflict_status = "conflict_detected"

    party = LawParties(
        case_id=case_id,
        office_id=office_id,
        name=safe_name,
        role_key=sanitize_input(role_key, 50),
        party_type=sanitize_input(party_type, 30),
        nationality=sanitize_input(nationality, 50),
        id_number=sanitize_input(id_number, 50),
        cr_number=sanitize_input(cr_number, 50),
        legal_capacity=sanitize_input(legal_capacity, 50),
        representation_status=sanitize_input(representation_status, 50),
        phone=sanitize_input(phone, 30),
        alt_phone=sanitize_input(alt_phone, 30),
        email=sanitize_input(email, 100),
        city=sanitize_input(city, 50),
        address=sanitize_input(address, 255),
        national_address=sanitize_input(national_address, 255),
        service_method=sanitize_input(service_method, 50),
        lawyer_name=sanitize_input(lawyer_name, 150),
        lawyer_phone=sanitize_input(lawyer_phone, 30),
        lawyer_license_no=sanitize_input(lawyer_license_no, 50),
        poa_number=sanitize_input(poa_number, 50),
        poa_date=sanitize_input(poa_date, 30),
        conflict_status=final_conflict_status,
        internal_notes=sanitize_input(internal_notes, 2000),
        is_active=1
    )
    db.add(party)
    db.commit()

    log_party_audit(db, office_id, user, "إضافة طرف قضائي", party, f"في القضية: {case.case_number}")

    if redirect_to == "parties":
        return RedirectResponse(url="/parties?msg=added", status_code=303)
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)


@router.post("/parties/edit")
async def edit_party(
    request: Request,
    party_id: int = Form(...),
    case_id: int = Form(...),
    name: str = Form(...),
    role_key: str = Form(...),
    party_type: str = Form("individual"),
    nationality: str = Form(None),
    id_number: str = Form(None),
    cr_number: str = Form(None),
    legal_capacity: str = Form(None),
    representation_status: str = Form(None),
    phone: str = Form(None),
    alt_phone: str = Form(None),
    email: str = Form(None),
    city: str = Form(None),
    address: str = Form(None),
    national_address: str = Form(None),
    service_method: str = Form(None),
    lawyer_name: str = Form(None),
    lawyer_phone: str = Form(None),
    lawyer_license_no: str = Form(None),
    poa_number: str = Form(None),
    poa_date: str = Form(None),
    conflict_status: str = Form("clear"),
    internal_notes: str = Form(None),
    redirect_to: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    if not office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")

    party = db.query(LawParties).filter(
        LawParties.id == party_id,
        LawParties.office_id == office_id,
        LawParties.is_deleted == 0
    ).first()
    if not party:
        raise HTTPException(status_code=404, detail="الطرف القضائي غير موجود")

    # IDOR Check: Ensure destination case belongs to the tenant's office
    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0
    ).first()
    if not case:
        raise HTTPException(status_code=403, detail="غير مصرح بتعديل هذا الطرف")

    # RBAC Check: Ensure assigned lawyer if restricted
    if user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0 and case.lead_lawyer_id != user.id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل أطراف هذه القضية")

    safe_name = sanitize_input(name, 200)
    if not safe_name:
        raise HTTPException(status_code=400, detail="اسم الطرف مطلوب")

    party.case_id = case_id
    party.name = safe_name
    party.role_key = sanitize_input(role_key, 50)
    party.party_type = sanitize_input(party_type, 30)
    party.nationality = sanitize_input(nationality, 50)
    party.id_number = sanitize_input(id_number, 50)
    party.cr_number = sanitize_input(cr_number, 50)
    party.legal_capacity = sanitize_input(legal_capacity, 50)
    party.representation_status = sanitize_input(representation_status, 50)
    party.phone = sanitize_input(phone, 30)
    party.alt_phone = sanitize_input(alt_phone, 30)
    party.email = sanitize_input(email, 100)
    party.city = sanitize_input(city, 50)
    party.address = sanitize_input(address, 255)
    party.national_address = sanitize_input(national_address, 255)
    party.service_method = sanitize_input(service_method, 50)
    party.lawyer_name = sanitize_input(lawyer_name, 150)
    party.lawyer_phone = sanitize_input(lawyer_phone, 30)
    party.lawyer_license_no = sanitize_input(lawyer_license_no, 50)
    party.poa_number = sanitize_input(poa_number, 50)
    party.poa_date = sanitize_input(poa_date, 30)
    party.conflict_status = conflict_status or party.conflict_status
    party.internal_notes = sanitize_input(internal_notes, 2000)

    db.commit()
    log_party_audit(db, office_id, user, "تعديل طرف قضائي", party, f"تم التحديث في القضية: {case.case_number}")

    if redirect_to == "parties":
        return RedirectResponse(url="/parties?msg=updated", status_code=303)
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)


@router.post("/parties/delete")
async def delete_party(
    request: Request,
    party_id: int = Form(...),
    case_id: int = Form(None),
    redirect_to: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """Soft Delete for Parties to preserve court records & audit log"""
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    if not office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")

    party = db.query(LawParties).filter(
        LawParties.id == party_id,
        LawParties.office_id == office_id,
        LawParties.is_deleted == 0
    ).first()
    if not party:
        raise HTTPException(status_code=404, detail="الطرف غير موجود")

    # RBAC Check: Ensure assigned lawyer if restricted
    if party.case_id and user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0:
        c = db.query(LawCases).filter(LawCases.id == party.case_id).first()
        if c and c.lead_lawyer_id != user.id:
            raise HTTPException(status_code=403, detail="غير مصرح لك بحذف أطراف هذه القضية")

    party.is_deleted = 1
    db.commit()

    log_party_audit(db, office_id, user, "حذف طرف قضائي", party, "تم نقل الطرف لسجل الأطراف المحذوفة بأمان")

    if redirect_to == "parties" or not case_id:
        return RedirectResponse(url="/parties?msg=deleted", status_code=303)
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)


@router.get("/api/parties/{party_id}")
async def get_party_details(
    party_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """Secure JSON API for Party View & Edit Modals"""
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    office_id = user.office_id
    p = db.query(LawParties).filter(
        LawParties.id == party_id,
        LawParties.office_id == office_id,
        LawParties.is_deleted == 0
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="الطرف غير موجود")

    can_view_internal = (user.role in ['مدير المكتب', 'المسؤول', 'أدمن', 'محامي', 'محامٍ'])

    return {
        "id": p.id,
        "name": p.name,
        "role_key": p.role_key,
        "party_type": p.party_type or "individual",
        "nationality": p.nationality or "",
        "id_number": p.id_number or "",
        "cr_number": p.cr_number or "",
        "legal_capacity": p.legal_capacity or "",
        "representation_status": p.representation_status or "اصيل",
        "phone": p.phone or "",
        "alt_phone": p.alt_phone or "",
        "email": p.email or "",
        "city": p.city or "",
        "address": p.address or "",
        "national_address": p.national_address or "",
        "service_method": p.service_method or "",
        "lawyer_name": p.lawyer_name or "",
        "lawyer_phone": p.lawyer_phone or "",
        "lawyer_license_no": p.lawyer_license_no or "",
        "poa_number": p.poa_number or "",
        "poa_date": p.poa_date or "",
        "conflict_status": p.conflict_status or "clear",
        "internal_notes": (p.internal_notes or "") if can_view_internal else "",
        "case_id": p.case_id,
        "case_number": p.law_case.case_number if p.law_case else "",
        "case_title": p.law_case.title if p.law_case else "",
        "created_at": p.created_at or ""
    }
