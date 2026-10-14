# -*- coding: utf-8 -*-
"""
مسار إدارة واجهة «القضايا الواردة» في نظام إدارة مكتب المحاماة
يغطي الأقسام الخمسة المستقلة:
1. القضايا الواردة من الشرطة
2. القضايا الواردة من النيابة العامة
3. القضايا الواردة من المحكمة الابتدائية
4. القضايا الواردة من المحكمة الاستئنافية
5. القضايا الواردة من التنفيذ
مع احترام بنية قاعدة البيانات الحالية ومنع التكرار وربط الموكلين والمستندات وسجل التدقيق.
"""

import os
import uuid
import json
import secrets
import hashlib
import base64
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func

from database.database import get_db
from database.models import (
    AccessProfiles,
    LawOffices,
    LawClients,
    LawCases,
    LawDocuments,
    LawAuditLog,
    LawIncomingCases,
)
from dependencies import get_current_user, templates, check_user_permission
from core.security import validate_file_signature

router = APIRouter(prefix="/incoming-cases", tags=["Incoming Cases Reception"])

DOCUMENTS_UPLOAD_DIR = "private_uploads/documents"
os.makedirs(DOCUMENTS_UPLOAD_DIR, exist_ok=True)

SECTION_CONFIG = {
    "police": {
        "key": "police",
        "num": "1",
        "title": "القضايا الواردة من الشرطة",
        "badge_color": "#2563eb",
        "icon": "fa-solid fa-shield-halved",
        "ref_field_label": "رقم المحضر / البلاغ",
        "authority_field_label": "الجهة الشرطية",
        "base_number": 1000,
    },
    "prosecution": {
        "key": "prosecution",
        "num": "2",
        "title": "القضايا الواردة من النيابة العامة",
        "badge_color": "#059669",
        "icon": "fa-solid fa-scale-balanced",
        "ref_field_label": "رقم الملف لدى النيابة",
        "authority_field_label": "اسم النيابة",
        "base_number": 2000,
    },
    "first_instance": {
        "key": "first_instance",
        "num": "3",
        "title": "القضايا الواردة من المحكمة الابتدائية",
        "badge_color": "#7c3aed",
        "icon": "fa-solid fa-landmark",
        "ref_field_label": "رقم القضية",
        "authority_field_label": "اسم المحكمة",
        "base_number": 3000,
    },
    "appeal": {
        "key": "appeal",
        "num": "4",
        "title": "القضايا الواردة من المحكمة الاستئنافية",
        "badge_color": "#ea580c",
        "icon": "fa-solid fa-scale-unbalanced",
        "ref_field_label": "رقم القضية الاستئنافية",
        "authority_field_label": "محكمة الاستئناف",
        "base_number": 4000,
    },
    "enforcement": {
        "key": "enforcement",
        "num": "5",
        "title": "القضايا الواردة من التنفيذ",
        "badge_color": "#0d9488",
        "icon": "fa-solid fa-gavel",
        "ref_field_label": "رقم ملف التنفيذ",
        "authority_field_label": "جهة التنفيذ",
        "base_number": 5000,
    },
}


def log_incoming_audit(
    db: Session,
    office_id: int,
    user: AccessProfiles,
    action_name: str,
    record: LawIncomingCases,
    details: str = "",
):
    """توثيق العمليات في سجل التدقيق المعتمد بالنظام"""
    try:
        audit = LawAuditLog(
            table_name="law_incoming_cases",
            action_name=action_name,
            record_key=str(record.id),
            actor_name=getattr(user, "name", "") or getattr(user, "username", "مستخدم"),
            actor_user_id=user.id,
            office_id=office_id,
            details=f"ملف وارد #{record.internal_number} ({record.section_key}) | موكل: {record.client_name or '-'} | {details}",
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        print(f"[Audit Log Error] {e}")


def generate_internal_number(db: Session, office_id: int, section_key: str) -> str:
    """توليد رقم داخلي فريد ومتسلسل وفق نطاق القسم (1001, 2001, 3001, 4001, 5001)"""
    cfg = SECTION_CONFIG.get(section_key, {"base_number": 1000})
    base_num = cfg["base_number"]

    existing = (
        db.query(LawIncomingCases.internal_number)
        .filter(
            LawIncomingCases.office_id == office_id,
            LawIncomingCases.section_key == section_key,
        )
        .all()
    )

    max_num = base_num
    for (val,) in existing:
        if val and str(val).isdigit():
            v_int = int(val)
            if v_int > max_num:
                max_num = v_int

    return str(max_num + 1)


# ============================================================================
# 1. الشاشة الرئيسية لـ «القضايا الواردة» (Hub: البطاقات الخمس)
# ============================================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def incoming_cases_hub(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not user.office_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمكتب")

    # إحصائيات الأقسام الخمسة
    section_stats = {}
    for sec_key in SECTION_CONFIG.keys():
        count = (
            db.query(LawIncomingCases)
            .filter(
                LawIncomingCases.office_id == user.office_id,
                LawIncomingCases.section_key == sec_key,
                LawIncomingCases.is_deleted == 0,
            )
            .count()
        )
        section_stats[sec_key] = count

    # إحصائيات عامة
    total_files = sum(section_stats.values())
    pending_count = (
        db.query(LawIncomingCases)
        .filter(
            LawIncomingCases.office_id == user.office_id,
            LawIncomingCases.status_key == "under_review",
            LawIncomingCases.is_deleted == 0,
        )
        .count()
    )
    completed_count = (
        db.query(LawIncomingCases)
        .filter(
            LawIncomingCases.office_id == user.office_id,
            LawIncomingCases.status_key == "completed",
            LawIncomingCases.is_deleted == 0,
        )
        .count()
    )
    incomplete_count = (
        db.query(LawIncomingCases)
        .filter(
            LawIncomingCases.office_id == user.office_id,
            LawIncomingCases.status_key == "incomplete",
            LawIncomingCases.is_deleted == 0,
        )
        .count()
    )

    # إجمالي القضايا الفريدة المسجلة بالنظام (لتوضيح الفرق الإحصائي للوثيقة)
    unique_cases_count = (
        db.query(LawCases)
        .filter(
            LawCases.office_id == user.office_id,
            LawCases.is_deleted == 0,
        )
        .count()
    )

    return templates.TemplateResponse(
        "incoming_cases/hub.html",
        {
            "request": request,
            "user": user,
            "active_page": "incoming_cases",
            "section_stats": section_stats,
            "total_files": total_files,
            "pending_count": pending_count,
            "completed_count": completed_count,
            "incomplete_count": incomplete_count,
            "unique_cases_count": unique_cases_count,
            "sections": SECTION_CONFIG,
        },
    )


# ============================================================================
# 2. شاشات الأقسام الخمسة (Split View: جدول السجلات + نموذج الاستقبال)
# ============================================================================

@router.get("/{section_key}", response_class=HTMLResponse)
async def incoming_cases_section_view(
    section_key: str,
    request: Request,
    q: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    per_page: int = 15,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not user.office_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمكتب")

    if section_key not in SECTION_CONFIG:
        raise HTTPException(status_code=404, detail="قسم الاستقبال غير معروف")

    cfg = SECTION_CONFIG[section_key]

    # جلب الموكلين لربطهم في النموذج
    clients = (
        db.query(LawClients)
        .filter(
            LawClients.office_id == user.office_id,
            LawClients.is_deleted == 0,
        )
        .order_by(LawClients.name.asc())
        .all()
    )

    # جلب القضايا القائمة للربط الاختياري
    cases = (
        db.query(LawCases)
        .filter(
            LawCases.office_id == user.office_id,
            LawCases.is_deleted == 0,
        )
        .order_by(LawCases.case_number.asc())
        .all()
    )

    # استعلام السجلات المسجلة لهذا القسم
    query = db.query(LawIncomingCases).filter(
        LawIncomingCases.office_id == user.office_id,
        LawIncomingCases.section_key == section_key,
        LawIncomingCases.is_deleted == 0,
    )

    # فلترة البحث
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                LawIncomingCases.internal_number.ilike(term),
                LawIncomingCases.client_name.ilike(term),
                LawIncomingCases.police_report_number.ilike(term),
                LawIncomingCases.police_station.ilike(term),
                LawIncomingCases.prosecution_file_number.ilike(term),
                LawIncomingCases.prosecution_name.ilike(term),
                LawIncomingCases.court_case_number.ilike(term),
                LawIncomingCases.court_name.ilike(term),
                LawIncomingCases.appeal_case_number.ilike(term),
                LawIncomingCases.appeal_court_name.ilike(term),
                LawIncomingCases.enforcement_file_number.ilike(term),
                LawIncomingCases.enforcement_authority.ilike(term),
                LawIncomingCases.subject_description.ilike(term),
            )
        )

    # فلترة الحالة
    if status_filter and status_filter.strip():
        query = query.filter(LawIncomingCases.status_key == status_filter.strip())

    total_records = query.count()
    total_pages = max(1, (total_records + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    records = (
        query.order_by(desc(LawIncomingCases.id))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # تجهيز رقم داخلي مقترح جديد
    suggested_internal_number = generate_internal_number(db, user.office_id, section_key)
    today_date = datetime.now().strftime("%Y-%m-%d")

    return templates.TemplateResponse(
        "incoming_cases/section_view.html",
        {
            "request": request,
            "user": user,
            "active_page": "incoming_cases",
            "section_key": section_key,
            "cfg": cfg,
            "records": records,
            "clients": clients,
            "cases": cases,
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "q": q or "",
            "status_filter": status_filter or "",
            "suggested_internal_number": suggested_internal_number,
            "today_date": today_date,
            "all_sections": SECTION_CONFIG,
        },
    )


# ============================================================================
# 3. تسجيل ملف وارد جديد (Save Incoming Case)
# ============================================================================

@router.post("/{section_key}/create")
async def create_incoming_case(
    section_key: str,
    request: Request,
    client_id: Optional[int] = Form(None),
    client_name_input: Optional[str] = Form(None),
    case_id: Optional[int] = Form(None),
    reception_date: Optional[str] = Form(None),
    status_key: str = Form("under_review"),
    subject_description: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    # Police fields
    police_station: Optional[str] = Form(None),
    police_report_number: Optional[str] = Form(None),
    document_date: Optional[str] = Form(None),
    police_referral_status: Optional[str] = Form(None),
    # Prosecution fields
    prosecution_name: Optional[str] = Form(None),
    prosecution_file_number: Optional[str] = Form(None),
    prosecution_decision_date: Optional[str] = Form(None),
    # First instance fields
    court_name: Optional[str] = Form(None),
    court_case_number: Optional[str] = Form(None),
    case_year: Optional[str] = Form(None),
    judicial_document_type: Optional[str] = Form(None),
    client_capacity: Optional[str] = Form(None),
    # Appeal fields
    appeal_court_name: Optional[str] = Form(None),
    appeal_case_number: Optional[str] = Form(None),
    appeal_year: Optional[str] = Form(None),
    primary_case_number: Optional[str] = Form(None),
    primary_judgment_date: Optional[str] = Form(None),
    # Enforcement fields
    enforcement_authority: Optional[str] = Form(None),
    enforcement_file_number: Optional[str] = Form(None),
    enforcement_document_type: Optional[str] = Form(None),
    enforcement_parties: Optional[str] = Form(None),
    enforcement_document_date: Optional[str] = Form(None),
    # Uploaded files
    files: List[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not user.office_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمكتب")

    if section_key not in SECTION_CONFIG:
        raise HTTPException(status_code=400, detail="القسم غير صالح")

    # تحديد اسم الموكل
    final_client_id = client_id
    final_client_name = ""
    if client_id:
        client_obj = (
            db.query(LawClients)
            .filter(LawClients.id == client_id, LawClients.office_id == user.office_id)
            .first()
        )
        if client_obj:
            final_client_name = client_obj.name
    elif client_name_input and client_name_input.strip():
        # إنشاء موكل جديد مباشرة لمنع التعطيل ولتسهيل الاستقبال
        clean_name = client_name_input.strip()
        new_client = LawClients(
            office_id=user.office_id,
            name=clean_name,
            client_type="individual",
            notes="تم إنشاؤه تلقائياً أثناء استقبال ملف وارد",
        )
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
        final_client_id = new_client.id
        final_client_name = new_client.name

    if not final_client_name:
        final_client_name = "موكل مجهول / قيد التحديد"

    # تاريخ الاستلام
    final_reception_date = reception_date or datetime.now().strftime("%Y-%m-%d")

    # توليد الرقم الداخلي الفريد
    internal_number = generate_internal_number(db, user.office_id, section_key)

    # معالجة الملفات المرفقة
    attachments_list = []
    if files:
        allowed_exts = {"pdf", "doc", "docx", "jpg", "jpeg", "png", "txt"}
        MAX_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

        for f in files:
            if not f or not f.filename:
                continue
            orig_name = os.path.basename(f.filename)
            clean_fn = "".join(c for c in orig_name if c.isalnum() or c in " ._-")
            ext = clean_fn.split(".")[-1].lower() if "." in clean_fn else ""
            if ext not in allowed_exts:
                continue

            file_bytes = await f.read(MAX_SIZE_BYTES + 1)
            if len(file_bytes) > MAX_SIZE_BYTES:
                continue

            if not validate_file_signature(file_bytes, ext):
                continue

            saved_name = f"{uuid.uuid4().hex}.{ext}"
            saved_path = os.path.join(DOCUMENTS_UPLOAD_DIR, saved_name)
            with open(saved_path, "wb") as f_out:
                f_out.write(file_bytes)

            file_path_str = f"{DOCUMENTS_UPLOAD_DIR}/{saved_name}"

            # إدراج في المستندات العامة للنظام أيضاً للتكامل التام
            doc_code = f"REC-{internal_number}-{len(attachments_list)+1}"
            law_doc = LawDocuments(
                office_id=user.office_id,
                case_id=case_id,
                client_id=final_client_id,
                name=orig_name,
                document_type_key="incoming_file",
                doc_code=doc_code,
                doc_date=document_date or final_reception_date,
                received_date=final_reception_date,
                description=f"مستند مرفق باستقبال ملف وارد #{internal_number} ({SECTION_CONFIG[section_key]['title']})",
                file_path=file_path_str,
                file_size=len(file_bytes),
                file_type=ext,
                is_archived=0,
                created_by_user_id=user.id,
            )
            db.add(law_doc)

            attachments_list.append(
                {
                    "name": orig_name,
                    "path": file_path_str,
                    "size": len(file_bytes),
                    "type": ext,
                    "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            )

    attachments_json_str = json.dumps(attachments_list, ensure_ascii=False) if attachments_list else None

    # إنشاء سجل الاستقبال
    incoming_record = LawIncomingCases(
        office_id=user.office_id,
        section_key=section_key,
        internal_number=internal_number,
        client_id=final_client_id,
        client_name=final_client_name,
        case_id=case_id,
        reception_date=final_reception_date,
        status_key=status_key or "under_review",
        subject_description=subject_description,
        notes=notes,
        created_by_user_id=user.id,
        # Police
        police_station=police_station,
        police_report_number=police_report_number,
        document_date=document_date,
        police_referral_status=police_referral_status,
        # Prosecution
        prosecution_name=prosecution_name,
        prosecution_file_number=prosecution_file_number,
        prosecution_decision_date=prosecution_decision_date,
        # First instance
        court_name=court_name,
        court_case_number=court_case_number,
        case_year=case_year,
        judicial_document_type=judicial_document_type,
        client_capacity=client_capacity,
        # Appeal
        appeal_court_name=appeal_court_name,
        appeal_case_number=appeal_case_number,
        appeal_year=appeal_year,
        primary_case_number=primary_case_number,
        primary_judgment_date=primary_judgment_date,
        # Enforcement
        enforcement_authority=enforcement_authority,
        enforcement_file_number=enforcement_file_number,
        enforcement_document_type=enforcement_document_type,
        enforcement_parties=enforcement_parties,
        enforcement_document_date=enforcement_document_date,
        # Attachments
        attachments_json=attachments_json_str,
    )

    db.add(incoming_record)
    db.commit()
    db.refresh(incoming_record)

    log_incoming_audit(
        db,
        user.office_id,
        user,
        "تسجيل ملف وارد جديد",
        incoming_record,
        f"تم استقبال الملف بنجاح برقم {internal_number}",
    )

    return RedirectResponse(
        url=f"/incoming-cases/{section_key}?msg=created&saved_id={incoming_record.id}",
        status_code=303,
    )


# ============================================================================
# 4. واجهات API المساعدة (تفاصيل، فحص تكرار، إضافة موكل سريع، إلغاء، تحويل)
# ============================================================================

@router.get("/api/details/{record_id}")
async def get_incoming_case_details(
    record_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    """جلب التفاصيل الكاملة لملف الاستقبال لفتحها في نافذة العرض والتعديل"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")

    item = (
        db.query(LawIncomingCases)
        .filter(
            LawIncomingCases.id == record_id,
            LawIncomingCases.office_id == user.office_id,
            LawIncomingCases.is_deleted == 0,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="الملف الوارد غير موجود")

    attachments = []
    if item.attachments_json:
        try:
            attachments = json.loads(item.attachments_json)
        except:
            attachments = []

    cfg = SECTION_CONFIG.get(item.section_key, {})

    return {
        "id": item.id,
        "office_id": item.office_id,
        "section_key": item.section_key,
        "section_title": cfg.get("title", ""),
        "internal_number": item.internal_number,
        "client_id": item.client_id,
        "client_name": item.client_name or (item.law_client.name if item.law_client else ""),
        "case_id": item.case_id,
        "case_number": item.law_case.case_number if item.law_case else "",
        "reception_date": item.reception_date,
        "status_key": item.status_key,
        "subject_description": item.subject_description or "",
        "notes": item.notes or "",
        "created_by": item.created_by.name if item.created_by else "النظام",
        "created_at": item.created_at,
        "is_cancelled": item.is_cancelled,
        "cancellation_reason": item.cancellation_reason or "",
        # Police
        "police_station": item.police_station or "",
        "police_report_number": item.police_report_number or "",
        "document_date": item.document_date or "",
        "police_referral_status": item.police_referral_status or "",
        # Prosecution
        "prosecution_name": item.prosecution_name or "",
        "prosecution_file_number": item.prosecution_file_number or "",
        "prosecution_decision_date": item.prosecution_decision_date or "",
        # First instance
        "court_name": item.court_name or "",
        "court_case_number": item.court_case_number or "",
        "case_year": item.case_year or "",
        "judicial_document_type": item.judicial_document_type or "",
        "client_capacity": item.client_capacity or "",
        # Appeal
        "appeal_court_name": item.appeal_court_name or "",
        "appeal_case_number": item.appeal_case_number or "",
        "appeal_year": item.appeal_year or "",
        "primary_case_number": item.primary_case_number or "",
        "primary_judgment_date": item.primary_judgment_date or "",
        # Enforcement
        "enforcement_authority": item.enforcement_authority or "",
        "enforcement_file_number": item.enforcement_file_number or "",
        "enforcement_document_type": item.enforcement_document_type or "",
        "enforcement_parties": item.enforcement_parties or "",
        "enforcement_document_date": item.enforcement_document_date or "",
        # Attachments
        "attachments": attachments,
    }


@router.post("/api/update/{record_id}")
async def update_incoming_case(
    record_id: int,
    request: Request,
    status_key: str = Form("under_review"),
    subject_description: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    client_id: Optional[int] = Form(None),
    case_id: Optional[int] = Form(None),
    # Section specific updates
    ref_number: Optional[str] = Form(None),
    authority_name: Optional[str] = Form(None),
    doc_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    """تعديل بيانات ملف وارد قائم وفق الصلاحيات"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")

    item = (
        db.query(LawIncomingCases)
        .filter(
            LawIncomingCases.id == record_id,
            LawIncomingCases.office_id == user.office_id,
            LawIncomingCases.is_deleted == 0,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="الملف الوارد غير موجود")

    item.status_key = status_key
    item.subject_description = subject_description
    item.notes = notes
    item.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if client_id:
        item.client_id = client_id
        cl = db.query(LawClients).filter(LawClients.id == client_id).first()
        if cl:
            item.client_name = cl.name

    if case_id is not None:
        item.case_id = case_id if case_id > 0 else None

    # تحديث الحقول بحسب القسم
    if item.section_key == "police":
        if ref_number:
            item.police_report_number = ref_number
        if authority_name:
            item.police_station = authority_name
        if doc_date:
            item.document_date = doc_date
    elif item.section_key == "prosecution":
        if ref_number:
            item.prosecution_file_number = ref_number
        if authority_name:
            item.prosecution_name = authority_name
        if doc_date:
            item.prosecution_decision_date = doc_date
    elif item.section_key == "first_instance":
        if ref_number:
            item.court_case_number = ref_number
        if authority_name:
            item.court_name = authority_name
    elif item.section_key == "appeal":
        if ref_number:
            item.appeal_case_number = ref_number
        if authority_name:
            item.appeal_court_name = authority_name
    elif item.section_key == "enforcement":
        if ref_number:
            item.enforcement_file_number = ref_number
        if authority_name:
            item.enforcement_authority = authority_name
        if doc_date:
            item.enforcement_document_date = doc_date

    db.commit()
    log_incoming_audit(
        db,
        user.office_id,
        user,
        "تعديل ملف وارد",
        item,
        f"تم تحديث بيانات الملف #{item.internal_number}",
    )

    return JSONResponse({"success": True, "message": "تم تحديث الملف بنجاح"})


@router.post("/api/cancel/{record_id}")
async def cancel_incoming_case(
    record_id: int,
    request: Request,
    reason: str = Form(""),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    """إلغاء ملف الاستقبال بصورة منفصلة مع توثيق السبب ودون حذف الموكل أو القضية"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")

    item = (
        db.query(LawIncomingCases)
        .filter(
            LawIncomingCases.id == record_id,
            LawIncomingCases.office_id == user.office_id,
            LawIncomingCases.is_deleted == 0,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="الملف غير موجود")

    item.is_cancelled = 1
    item.cancellation_reason = reason.strip() or "تم الإلغاء بواسطة المستخدم"
    item.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()

    log_incoming_audit(
        db,
        user.office_id,
        user,
        "إلغاء ملف وارد",
        item,
        f"سبب الإلغاء: {item.cancellation_reason}",
    )

    return JSONResponse({"success": True, "message": "تم إلغاء ملف الاستقبال بنجاح"})


@router.get("/api/check-duplicate")
async def check_duplicate_incoming_case(
    section_key: str,
    ref_number: str,
    authority: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    """
    فحص احتمالية تكرار الملف وتنبيه المستخدم دون حظر قسري
    """
    if not user or not user.office_id or not ref_number or not ref_number.strip():
        return JSONResponse({"duplicate": False})

    ref = ref_number.strip()
    query = db.query(LawIncomingCases).filter(
        LawIncomingCases.office_id == user.office_id,
        LawIncomingCases.section_key == section_key,
        LawIncomingCases.is_deleted == 0,
    )

    if section_key == "police":
        query = query.filter(LawIncomingCases.police_report_number == ref)
    elif section_key == "prosecution":
        query = query.filter(LawIncomingCases.prosecution_file_number == ref)
    elif section_key == "first_instance":
        query = query.filter(LawIncomingCases.court_case_number == ref)
    elif section_key == "appeal":
        query = query.filter(LawIncomingCases.appeal_case_number == ref)
    elif section_key == "enforcement":
        query = query.filter(LawIncomingCases.enforcement_file_number == ref)

    existing = query.first()
    if existing:
        return JSONResponse(
            {
                "duplicate": True,
                "message": f"تنبيه: يوجد ملف وارد مسجل مسبقاً بنفس الرقم الداخلي ({existing.internal_number}) للموكل ({existing.client_name or '-'}) بتاريخ {existing.reception_date}.",
                "existing_id": existing.id,
                "internal_number": existing.internal_number,
            }
        )

    return JSONResponse({"duplicate": False})


@router.post("/api/quick-client")
async def quick_create_client(
    name: str = Form(...),
    phone: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    """إضافة موكل سريع من نافذة الاستقبال دون مغادرة الشاشة"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")

    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="اسم الموكل مطلوب")

    # التحقق من عدم وجود موكل بنفس الاسم أو الهاتف
    existing = (
        db.query(LawClients)
        .filter(
            LawClients.office_id == user.office_id,
            LawClients.name == clean_name,
            LawClients.is_deleted == 0,
        )
        .first()
    )
    if existing:
        return JSONResponse(
            {
                "success": True,
                "client_id": existing.id,
                "client_name": existing.name,
                "is_existing": True,
                "message": "تم اختيار الموكل المسجل مسبقاً بنفس الاسم",
            }
        )

    new_client = LawClients(
        office_id=user.office_id,
        name=clean_name,
        phone=phone.strip() if phone else None,
        national_id=national_id.strip() if national_id else None,
        client_type="individual",
        notes="تمت الإضافة السريعة من واجهة القضايا الواردة",
    )
    db.add(new_client)
    db.commit()
    db.refresh(new_client)

    return JSONResponse(
        {
            "success": True,
            "client_id": new_client.id,
            "client_name": new_client.name,
            "is_existing": False,
            "message": "تم تسجيل الموكل الجديد بنجاح",
        }
    )


def _hash_client_pin(pin: str) -> str:
    pin = pin.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")).strip()
    salt = os.urandom(16)
    iterations = 260000
    actual = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode('utf-8').rstrip('=')
    hash_b64 = base64.b64encode(actual).decode('utf-8').rstrip('=')
    return f"pbkdf2:sha256:{iterations}${salt_b64}${hash_b64}"


@router.post("/api/add-full-client")
async def add_full_client_from_modal(
    request: Request,
    name: str = Form(...),
    client_type: str = Form("individual"),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    case_id: Optional[int] = Form(None),
    case_number: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    alt_phone: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    cr_number: Optional[str] = Form(None),
    legal_rep_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    portal_access: int = Form(0),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    """إضافة موكل كامل بجميع حقول النظام وبوابته من داخل نافذة الاستقبال"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")

    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="اسم الموكل مطلوب")

    # معالجة اسم المستخدم في حال تفعيل البوابة
    if portal_access == 1:
        if not username or not username.strip():
            username_val = f"cli_{secrets.token_hex(4)}"
        else:
            username_val = username.strip()

        existing = db.query(AccessProfiles).filter(AccessProfiles.username == username_val).first()
        if existing:
            username_val = f"{username_val}_{secrets.token_hex(2)}"
    else:
        username_val = username.strip() if username else None

    # معالجة القضية المرتبطة إن وجدت
    final_case_number = case_number
    if case_id and case_id > 0:
        target_case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == user.office_id).first()
        if target_case and not final_case_number:
            final_case_number = target_case.case_number

    new_client = LawClients(
        office_id=user.office_id,
        name=clean_name,
        client_type=client_type,
        case_id=case_id if case_id and case_id > 0 else None,
        case_number=final_case_number.strip() if final_case_number else None,
        phone=phone.strip() if phone else None,
        alt_phone=alt_phone.strip() if alt_phone else None,
        national_id=national_id.strip() if national_id else None,
        cr_number=cr_number.strip() if cr_number else None,
        legal_rep_name=legal_rep_name.strip() if legal_rep_name else None,
        email=email.strip() if email else None,
        city=city.strip() if city else None,
        address=address.strip() if address else None,
        notes=notes.strip() if notes else None,
        username=username_val,
        portal_access=portal_access,
    )
    db.add(new_client)

    # إنشاء حساب دخول للموكل إذا كان مطلوباً
    if portal_access == 1:
        client_pass = password.strip() if password and len(password.strip()) >= 8 else secrets.token_urlsafe(10)
        target_email = email.strip() if email else f"{username_val}@client.local"
        existing_profile = None
        if target_email or phone:
            conds = []
            if target_email:
                conds.append(AccessProfiles.email == target_email)
            if phone and phone.strip():
                conds.append(AccessProfiles.phone == phone.strip())
            existing_profile = db.query(AccessProfiles).filter(or_(*conds)).first()

        if existing_profile and existing_profile.role == 'موكل':
            new_client.user_id = existing_profile.id
        else:
            new_user = AccessProfiles(
                name=clean_name,
                username=username_val,
                email=target_email,
                phone=phone.strip() if phone else username_val,
                case_number=final_case_number or "",
                access_pin_hash=_hash_client_pin(client_pass),
                role='موكل',
                office_id=user.office_id,
                is_active=1,
                email_verified=1,
                state="active",
            )
            db.add(new_user)
            db.flush()
            new_client.user_id = new_user.id

    db.commit()
    db.refresh(new_client)

    return JSONResponse(
        {
            "success": True,
            "client_id": new_client.id,
            "client_name": new_client.name,
            "phone": new_client.phone or "",
            "message": "تم تسجيل الموكل الجديد بنجاح في النظام",
        }
    )



@router.post("/api/convert-to-case/{record_id}")
async def convert_incoming_to_case(
    record_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    """
    تحويل أو ربط ملف الاستقبال بقضية رسمية بعد موافقة المكتب على توكيلها
    """
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")

    item = (
        db.query(LawIncomingCases)
        .filter(
            LawIncomingCases.id == record_id,
            LawIncomingCases.office_id == user.office_id,
            LawIncomingCases.is_deleted == 0,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="الملف غير موجود")

    if item.case_id:
        return JSONResponse(
            {
                "success": False,
                "message": f"هذا الملف مرتبط بالفعل بالقضية رقم {item.law_case.case_number if item.law_case else item.case_id}",
            }
        )

    # توليد رقم قضية فريد متوافق مع النظام (CASE-YYYY-XXXX)
    curr_year = datetime.now().year
    prefix = f"CASE-{curr_year}-"
    cases_cnt = (
        db.query(LawCases)
        .filter(
            LawCases.office_id == user.office_id,
            LawCases.case_number.like(f"{prefix}%"),
        )
        .count()
    )
    new_case_number = f"{prefix}{cases_cnt + 1:04d}"

    # تحديد نوع القضية والدرجة
    litigation_map = {
        "police": "police_stage",
        "prosecution": "prosecution_stage",
        "first_instance": "first_instance",
        "appeal": "appeal",
        "enforcement": "enforcement",
    }
    court_name_val = item.court_name or item.appeal_court_name or item.enforcement_authority or item.prosecution_name or item.police_station

    case_title = item.subject_description or f"قضية واردة من {SECTION_CONFIG.get(item.section_key, {}).get('title', '')} - {item.client_name}"

    new_case = LawCases(
        office_id=user.office_id,
        case_number=new_case_number,
        title=case_title,
        summary=item.notes or "تم التحويل من واجهة استقبال القضايا الواردة",
        status_key="new",
        visibility_mode="private",
        open_date=datetime.now().strftime("%Y-%m-%d"),
        created_by_user_id=user.id,
        court_name=court_name_val,
        litigation_level_key=litigation_map.get(item.section_key, "first_instance"),
        court_case_number=item.court_case_number or item.appeal_case_number or item.enforcement_file_number or item.prosecution_file_number or item.police_report_number,
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    # ربط ملف الاستقبال بالقضية
    item.case_id = new_case.id
    item.status_key = "completed"
    item.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ربط الموكل بالقضية أيضاً إذا كان موجوداً
    if item.client_id:
        cl = db.query(LawClients).filter(LawClients.id == item.client_id).first()
        if cl and not cl.case_id:
            cl.case_id = new_case.id
            cl.case_number = new_case.case_number

    db.commit()

    log_incoming_audit(
        db,
        user.office_id,
        user,
        "تحويل ملف وارد إلى قضية رسمية",
        item,
        f"تم إنشاء وتوليد القضية الرسمية برقم {new_case.case_number}",
    )

    return JSONResponse(
        {
            "success": True,
            "message": f"تم تحويل الملف الوارد وإنشاء القضية الرسمية برقم ({new_case.case_number}) بنجاح!",
            "case_id": new_case.id,
            "case_number": new_case.case_number,
        }
    )
