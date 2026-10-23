from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawClients, LawParties
from dependencies import get_current_user

router = APIRouter()

@router.get("/api/case/{case_id}/recipients")
async def get_case_recipients(
    case_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case: return JSONResponse({"error": "not found"}, status_code=404)
    
    recipients = []
    # Clients
    clients = db.query(LawClients).filter(LawClients.case_id == case_id).all()
    for c in clients:
        recipients.append({
            "id": f"client_{c.id}", "name": c.name,
            "type": "موكل", "phone": c.phone or "",
            "email": c.email or "", "has_phone": bool(c.phone), "has_email": bool(c.email)
        })
    # Parties
    parties = db.query(LawParties).filter(LawParties.case_id == case_id).all()
    for p in parties:
        recipients.append({
            "id": f"party_{p.id}", "name": p.name,
            "type": p.role_key, "phone": p.phone or "",
            "email": p.email or "", "has_phone": bool(p.phone), "has_email": bool(p.email)
        })
    return JSONResponse({"recipients": recipients})


@router.get("/api/cases/search")
async def search_cases_api(
    q: str = "",
    limit: int = 15,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """
    البحث السريع الذكي عن القضايا برقم القضية أو عنوانها أو اسم الموكل،
    مع جلب بيانات الموكل والمحامي المسؤول لتمكين التعبئة التلقائية.
    """
    if not user:
        return JSONResponse({"cases": []}, status_code=401)

    office_id = user.office_id
    query = db.query(LawCases).filter(
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0
    )

    if q and q.strip():
        term = f"%{q.strip()}%"
        from sqlalchemy import or_
        query = query.outerjoin(LawCases.law_clients).filter(
            or_(
                LawCases.case_number.ilike(term),
                LawCases.title.ilike(term),
                LawCases.summary.ilike(term),
                LawCases.court_name.ilike(term),
                LawCases.consultation_client_name.ilike(term),
                LawClients.name.ilike(term),
                LawClients.phone.ilike(term)
            )
        ).distinct()

    cases = query.order_by(LawCases.updated_at.desc(), LawCases.id.desc()).limit(limit).all()

    # جلب أسماء المحامين
    lawyers_map = {m.id: (m.name or m.username) for m in db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id).all()}
    
    results = []
    for c in cases:
        client_name = c.consultation_client_name or ""
        client_id = None
        client_phone = ""
        if not client_name and c.law_clients:
            client_name = c.law_clients[0].name
            client_id = c.law_clients[0].id
            client_phone = c.law_clients[0].phone or ""

        results.append({
            "id": c.id,
            "case_number": c.case_number,
            "title": c.title,
            "status_key": c.status_key,
            "case_type_key": getattr(c, 'case_type_key', '') or "",
            "client_id": client_id,
            "client_name": client_name,
            "client_phone": client_phone,
            "lead_lawyer_id": c.lead_lawyer_id,
            "lead_lawyer_name": lawyers_map.get(c.lead_lawyer_id, ""),
            "court_name": getattr(c, 'court_name', None) or "",
            "open_date": c.open_date or "",
            "estimated_fee": c.estimated_fee or 0.0
        })

    return JSONResponse({"cases": results})


@router.get("/api/case/{case_id}/details")
async def get_case_details_api(
    case_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """جلب التفاصيل الكاملة لقضية معينة لغرض التعبئة التلقائية الفورية"""
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0
    ).first()

    if not case:
        return JSONResponse({"error": "not found"}, status_code=404)

    client_name = case.consultation_client_name or ""
    client_phone = ""
    client_id = None
    if not client_name and case.law_clients:
        client_name = case.law_clients[0].name
        client_phone = case.law_clients[0].phone or ""
        client_id = case.law_clients[0].id

    lead_lawyer = db.query(AccessProfiles).filter(AccessProfiles.id == case.lead_lawyer_id).first() if case.lead_lawyer_id else None

    return JSONResponse({
        "success": True,
        "case": {
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
            "case_type_key": getattr(case, 'case_type_key', '') or "",
            "client_id": client_id,
            "client_name": client_name,
            "client_phone": client_phone,
            "lead_lawyer_id": case.lead_lawyer_id,
            "lead_lawyer_name": (lead_lawyer.name or lead_lawyer.username) if lead_lawyer else "",
            "court_name": getattr(case, 'court_name', None) or "",
            "status_key": case.status_key,
            "open_date": case.open_date or "",
            "estimated_fee": case.estimated_fee or 0.0
        }
    })

