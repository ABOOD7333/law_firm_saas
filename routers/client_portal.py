from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import base64
import re
import hashlib
from datetime import datetime, timezone

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawDocuments, LawClients, Invoices, LawHearings,
    LawPowerOfAttorney, RetainerAgreements, IntakeSubmissions
)
from dependencies import templates, get_current_user
from core.security import client_records_for_user

router = APIRouter(prefix="/client-portal", tags=["Client Portal"])

def get_portal_user(user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/"})
    return user


def _client_records(db: Session, user: AccessProfiles):
    if user.role == "موكل":
        return client_records_for_user(db, user)
    # If lawyer/admin viewing the portal, fetch first client or office clients for preview
    return db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0
    ).limit(5).all()


def _client_case_query(db: Session, user: AccessProfiles):
    if user.role == "موكل":
        client_ids = [record.id for record in _client_records(db, user)]
        case_ids = db.query(LawClients.case_id).filter(
            LawClients.id.in_(client_ids),
            LawClients.office_id == user.office_id,
            LawClients.case_id.isnot(None),
            LawClients.is_deleted == 0,
        ) if client_ids else None

        query = db.query(LawCases).filter(
            LawCases.office_id == user.office_id,
            LawCases.is_deleted == 0,
        )
        return query.filter(LawCases.id.in_(case_ids)) if case_ids is not None else query.filter(False)
    else:
        # Lawyer / Admin Preview Mode: show office cases
        return db.query(LawCases).filter(
            LawCases.office_id == user.office_id,
            LawCases.is_deleted == 0
        )


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def client_dashboard(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_portal_user)):
    client_records = _client_records(db, user)
    client_ids = [record.id for record in client_records]
    cases_query = _client_case_query(db, user)
    total_cases = cases_query.count()

    # Pending invoices count
    inv_filter = [
        Invoices.office_id == user.office_id,
        Invoices.is_deleted == 0,
        Invoices.status.in_(["Unpaid", "Partial"])
    ]
    if user.role == "موكل":
        inv_filter.append(Invoices.client_id.in_(client_ids) if client_ids else False)

    pending_payments = db.query(func.count(Invoices.id)).filter(*inv_filter).scalar() or 0
    recent_cases = cases_query.order_by(LawCases.id.desc()).limit(4).all()

    # Total documents count
    case_ids = [c.id for c in cases_query.with_entities(LawCases.id).all()]
    # Documents have no explicit client-visibility field; keep them private by default.
    total_docs = 0 if user.role == "موكل" else (db.query(func.count(LawDocuments.id)).filter(
        LawDocuments.office_id == user.office_id,
        LawDocuments.is_deleted == 0,
        LawDocuments.case_id.in_(case_ids) if case_ids else False
    ).scalar() or 0)

    # Upcoming hearings
    upcoming_hearings = db.query(LawHearings).filter(
        LawHearings.office_id == user.office_id,
        LawHearings.is_deleted == 0,
        LawHearings.show_in_client_portal == 1,
        LawHearings.case_id.in_(case_ids) if case_ids else False
    ).order_by(LawHearings.hearing_at.asc()).limit(3).all()

    # Pending contracts & POAs
    from sqlalchemy import or_
    client_names = [c.name.strip() for c in client_records if c.name]
    if user.name and user.name.strip() not in client_names:
        client_names.append(user.name.strip())

    poa_conds = []
    if case_ids:
        poa_conds.append(LawPowerOfAttorney.case_id.in_(case_ids))
    if client_names:
        poa_conds.append(or_(*[LawPowerOfAttorney.principal_name.ilike(f"%{n}%") for n in client_names]))

    total_contracts = 0
    pending_contracts = 0
    if poa_conds or user.role != "موكل":
        q_poa = db.query(LawPowerOfAttorney).filter(
            LawPowerOfAttorney.office_id == user.office_id,
            LawPowerOfAttorney.is_deleted == 0
        )
        if user.role == "موكل" and poa_conds:
            q_poa = q_poa.filter(or_(*poa_conds))
        all_poas = q_poa.all()
        total_contracts = len(all_poas)
        pending_contracts = sum(1 for p in all_poas if getattr(p, 'is_signed', 0) == 0)

    return templates.TemplateResponse("client_portal/dashboard.html", {
        "request": request,
        "user": user,
        "total_cases": total_cases,
        "total_docs": total_docs,
        "total_contracts": total_contracts,
        "pending_contracts": pending_contracts,
        "pending_payments": pending_payments,
        "recent_cases": recent_cases,
        "upcoming_hearings": upcoming_hearings,
        "is_preview": (user.role != "موكل"),
        "active_page": "dashboard"
    })


@router.get("/cases", response_class=HTMLResponse)
async def client_cases(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_portal_user)):
    cases = _client_case_query(db, user).order_by(LawCases.id.desc()).all()

    return templates.TemplateResponse("client_portal/cases.html", {
        "request": request,
        "user": user,
        "cases": cases,
        "is_preview": (user.role != "موكل"),
        "active_page": "cases"
    })


@router.get("/finance", response_class=HTMLResponse)
async def client_finance(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_portal_user)):
    client_ids = [record.id for record in _client_records(db, user)]

    payments = []
    total_paid = 0.0
    total_due = 0.0

    inv_filter = [
        Invoices.office_id == user.office_id,
        Invoices.is_deleted == 0
    ]
    if user.role == "موكل":
        inv_filter.append(Invoices.client_id.in_(client_ids) if client_ids else False)

    payments = db.query(Invoices).filter(*inv_filter).order_by(Invoices.id.desc()).all()

    for p in payments:
        paid_val = float(p.amount_paid or 0)
        grand_val = float(p.grand_total or 0)
        total_paid += paid_val
        total_due += max(0.0, grand_val - paid_val)

    return templates.TemplateResponse("client_portal/finance.html", {
        "request": request,
        "user": user,
        "payments": payments,
        "total_paid": total_paid,
        "total_due": total_due,
        "is_preview": (user.role != "موكل"),
        "active_page": "finance"
    })


@router.get("/documents", response_class=HTMLResponse)
async def client_documents(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_portal_user)):
    case_ids = [case.id for case in _client_case_query(db, user).with_entities(LawCases.id).all()]
    documents = []

    if user.role != "موكل":
        doc_filter = [
            LawDocuments.office_id == user.office_id,
            LawDocuments.is_deleted == 0
        ]
        if case_ids:
            doc_filter.append(LawDocuments.case_id.in_(case_ids))

        documents = db.query(LawDocuments).filter(*doc_filter).order_by(LawDocuments.id.desc()).all()

    return templates.TemplateResponse("client_portal/documents.html", {
        "request": request,
        "user": user,
        "documents": documents,
        "is_preview": (user.role != "موكل"),
        "active_page": "documents"
    })


@router.get("/hearings", response_class=HTMLResponse)
async def client_hearings(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_portal_user)):
    case_ids = [case.id for case in _client_case_query(db, user).with_entities(LawCases.id).all()]
    hearings = []

    if case_ids or user.role != "موكل":
        h_filter = [
            LawHearings.office_id == user.office_id,
            LawHearings.is_deleted == 0,
            LawHearings.show_in_client_portal == 1
        ]
        if case_ids:
            h_filter.append(LawHearings.case_id.in_(case_ids))

        hearings = db.query(LawHearings).filter(*h_filter).order_by(LawHearings.hearing_at.asc()).all()

    return templates.TemplateResponse("client_portal/hearings.html", {
        "request": request,
        "user": user,
        "hearings": hearings,
        "is_preview": (user.role != "موكل"),
        "active_page": "hearings"
    })


@router.get("/contracts", response_class=HTMLResponse)
async def client_contracts(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_portal_user)):
    """عرض عقود التوكيل والوكالات الرسمية المطلوب توقيعها إلكترونياً من قبل الموكل."""
    client_records = _client_records(db, user)
    case_ids = [c.id for c in _client_case_query(db, user).with_entities(LawCases.id).all()]
    client_names = [c.name.strip() for c in client_records if c.name]
    if user.name and user.name.strip() not in client_names:
        client_names.append(user.name.strip())

    poa_list = []
    if user.role == "موكل":
        # جلب الوكالات الخاصة بقضايا الموكل أو باسمه
        from sqlalchemy import or_
        conds = []
        if case_ids:
            conds.append(LawPowerOfAttorney.case_id.in_(case_ids))
        if client_names:
            name_filters = [LawPowerOfAttorney.principal_name.ilike(f"%{name}%") for name in client_names]
            conds.append(or_(*name_filters))
        
        if conds:
            poa_list = db.query(LawPowerOfAttorney).filter(
                LawPowerOfAttorney.office_id == user.office_id,
                LawPowerOfAttorney.is_deleted == 0,
                or_(*conds)
            ).order_by(LawPowerOfAttorney.id.desc()).all()
    else:
        # معاينة المحامي/المشرف: عرض وكالات المكتب
        poa_list = db.query(LawPowerOfAttorney).filter(
            LawPowerOfAttorney.office_id == user.office_id,
            LawPowerOfAttorney.is_deleted == 0
        ).order_by(LawPowerOfAttorney.id.desc()).limit(15).all()

    # إحصائيات التوقيع
    pending_sign_count = sum(1 for p in poa_list if getattr(p, 'is_signed', 0) == 0)
    signed_count = sum(1 for p in poa_list if getattr(p, 'is_signed', 0) == 1)

    return templates.TemplateResponse("client_portal/contracts.html", {
        "request": request,
        "user": user,
        "poas": poa_list,
        "pending_sign_count": pending_sign_count,
        "signed_count": signed_count,
        "is_preview": (user.role != "موكل"),
        "active_page": "contracts"
    })


@router.post("/poa/{poa_id}/sign")
async def client_sign_poa(
    poa_id: int,
    request: Request,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_portal_user)
):
    """حفظ واعتماد التوقيع الإلكتروني للموكل على الوكالة الرسمية."""
    poa = db.query(LawPowerOfAttorney).filter(
        LawPowerOfAttorney.id == poa_id,
        LawPowerOfAttorney.office_id == user.office_id,
        LawPowerOfAttorney.is_deleted == 0
    ).first()

    if not poa:
        return JSONResponse({"ok": False, "error": "الوكالة الرسمية غير موجودة"}, status_code=404)

    if getattr(poa, 'is_signed', 0) == 1:
        return JSONResponse({"ok": False, "error": "تم توقيع هذه الوكالة مسبقاً بالفعل وموثقة في النظام"}, status_code=409)

    signature_base64 = data.get("signature")
    if not isinstance(signature_base64, str) or len(signature_base64) > 1_500_000:
        return JSONResponse({"ok": False, "error": "بيانات التوقيع غير مكتملة"}, status_code=400)

    match = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/]+={0,2})", signature_base64)
    if not match:
        return JSONResponse({"ok": False, "error": "صيغة التوقيع غير صالحة"}, status_code=400)

    try:
        signature_bytes = base64.b64decode(match.group(1), validate=True)
    except ValueError:
        return JSONResponse({"ok": False, "error": "صيغة التوقيع غير صالحة"}, status_code=400)

    if not signature_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return JSONResponse({"ok": False, "error": "محتوى التوقيع غير صالح"}, status_code=400)

    client_ip = request.client.host if request.client else "unknown"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # توليد بصمة تحقق مشفرة للوكالة والتوقيع
    sig_digest = hashlib.sha256(signature_bytes).hexdigest()
    raw_hash = f"{poa.id}-{poa.principal_name}-{poa.agency_number}-{sig_digest}-{now_str}-{client_ip}"
    v_hash = hashlib.sha256(raw_hash.encode()).hexdigest()[:16].upper()

    poa.is_signed = 1
    poa.signed_at = now_str
    poa.signature_base64 = signature_base64
    poa.signer_ip = client_ip
    poa.verification_hash = v_hash

    db.commit()

    return JSONResponse({
        "ok": True,
        "message": "تم توقيع عقد التوكيل الرسمي بنجاح وتوثيقه لدى المكتب",
        "signed_at": now_str,
        "verification_hash": v_hash
    })
