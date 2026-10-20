# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime
import json
import traceback
import os
import uuid
import re

from core.error_handler import safe_error_html
from database.database import get_db
from database.models import AccessProfiles, LawCases, LawDocuments, LawDocumentVersions, LawClients, LawAuditLog
from dependencies import get_current_user, templates, check_user_permission, user_can_access_case

router = APIRouter()

# Ensure private uploads folder exists
DOCUMENTS_UPLOAD_DIR = "private_uploads/documents"
os.makedirs(DOCUMENTS_UPLOAD_DIR, exist_ok=True)


def log_document_audit(db: Session, office_id: int, user: AccessProfiles, action_name: str, doc: LawDocuments, details: str = ""):
    """Helper to record document audit trail into law_audit_log"""
    try:
        audit = LawAuditLog(
            table_name="law_documents",
            action_name=action_name,
            record_key=str(doc.id),
            actor_name=getattr(user, "name", "") or getattr(user, "username", "مستخدم"),
            actor_user_id=user.id,
            office_id=office_id,
            details=f"مستند: {doc.name} (كود: {doc.doc_code or '-'}) | {details}"
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        print(f"[Audit Log Error] {e}")


def generate_document_code(db: Session, office_id: int) -> str:
    """Generate a clean, unique document reference code: DOC-YYYY-XXXX"""
    current_year = datetime.now().year
    prefix = f"DOC-{current_year}-"
    # Find max sequence for current year in the office
    existing_codes = db.query(LawDocuments.doc_code).filter(
        LawDocuments.office_id == office_id,
        LawDocuments.doc_code.like(f"{prefix}%")
    ).all()
    max_num = 0
    for (code,) in existing_codes:
        if code and code.startswith(prefix):
            try:
                num = int(code.split('-')[-1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
    next_num = max_num + 1
    return f"{prefix}{next_num:04d}"


@router.get("/documents", response_class=HTMLResponse)
async def documents_page(
    request: Request,
    view: str = "active",  # 'active', 'archived', 'all'
    q: str = None,
    doc_type: str = None,
    client_id: int = None,
    case_id: int = None,
    date_from: str = None,
    date_to: str = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "documents", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بعرض المستندات")
    try:
        if not user.office_id:
            raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")

        # Base query
        docs_query = db.query(LawDocuments).filter(
            LawDocuments.office_id == user.office_id,
            LawDocuments.is_deleted == 0
        )
        cases_query = db.query(LawCases).filter(
            LawCases.office_id == user.office_id,
            LawCases.is_deleted == 0
        )
        clients_query = db.query(LawClients).filter(
            LawClients.office_id == user.office_id
        )

        # RBAC: If lawyer and cannot view all cases, filter by their cases
        if user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0:
            accessible_case_ids = db.query(LawCases.id).filter(
                LawCases.office_id == user.office_id,
                LawCases.lead_lawyer_id == user.id,
                LawCases.is_deleted == 0,
            ).subquery()
            docs_query = docs_query.filter(LawDocuments.case_id.in_(accessible_case_ids))
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)

        # Archive filter
        if view == "archived":
            docs_query = docs_query.filter(LawDocuments.is_archived == 1)
        elif view == "all":
            pass  # show all
        else:  # default 'active'
            docs_query = docs_query.filter(or_(LawDocuments.is_archived == 0, LawDocuments.is_archived.is_(None)))

        # Search Query (Arabic & Multi-field)
        if q and q.strip():
            search_term = f"%{q.strip()}%"
            docs_query = docs_query.filter(
                or_(
                    LawDocuments.name.ilike(search_term),
                    LawDocuments.doc_code.ilike(search_term),
                    LawDocuments.description.ilike(search_term),
                    LawDocuments.keywords.ilike(search_term),
                    LawDocuments.notes.ilike(search_term)
                )
            )

        # Type Filter
        if doc_type and doc_type.strip():
            docs_query = docs_query.filter(LawDocuments.document_type_key == doc_type.strip())

        # Client Filter
        if client_id:
            docs_query = docs_query.filter(LawDocuments.client_id == client_id)

        # Case Filter
        if case_id:
            docs_query = docs_query.filter(LawDocuments.case_id == case_id)

        # Date Range Filter (doc_date or received_date)
        if date_from:
            docs_query = docs_query.filter(or_(LawDocuments.doc_date >= date_from, LawDocuments.received_date >= date_from))
        if date_to:
            docs_query = docs_query.filter(or_(LawDocuments.doc_date <= date_to, LawDocuments.received_date <= date_to))

        docs = docs_query.order_by(desc(LawDocuments.id)).all()
        cases = cases_query.order_by(LawCases.case_number.asc()).all()
        clients = clients_query.order_by(LawClients.name.asc()).all()

        # Generate a preview document code for the modal
        suggested_code = generate_document_code(db, user.office_id)
        today_date = datetime.now().strftime("%Y-%m-%d")

        # Serialized cases list for dynamic client-case linkage in JS
        cases_json = [
            {
                "id": c.id,
                "case_number": c.case_number,
                "title": c.title,
                "client_id": c.law_clients[0].id if c.law_clients else None,
                "client_name": c.law_clients[0].name if c.law_clients else ""
            }
            for c in cases
        ]

        # Count active vs archived for stats
        total_active = db.query(LawDocuments).filter(
            LawDocuments.office_id == user.office_id,
            LawDocuments.is_deleted == 0,
            or_(LawDocuments.is_archived == 0, LawDocuments.is_archived.is_(None))
        ).count()
        total_archived = db.query(LawDocuments).filter(
            LawDocuments.office_id == user.office_id,
            LawDocuments.is_deleted == 0,
            LawDocuments.is_archived == 1
        ).count()

        return templates.TemplateResponse(
            request=request,
            name="documents.html",
            context={
                "user": user,
                "docs": docs,
                "cases": cases,
                "clients": clients,
                "cases_json": cases_json,
                "suggested_code": suggested_code,
                "today_date": today_date,
                "current_view": view,
                "total_active": total_active,
                "total_archived": total_archived,
                "filters": {
                    "q": q or "",
                    "doc_type": doc_type or "",
                    "client_id": client_id or "",
                    "case_id": case_id or "",
                    "date_from": date_from or "",
                    "date_to": date_to or ""
                },
                "active_page": "documents"
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="documents_route.py")


@router.post("/documents/add")
async def add_document(
    request: Request,
    name: str = Form(...),
    document_type_key: str = Form(...),
    doc_code: str = Form(None),
    client_id: int = Form(None),
    case_id: int = Form(None),
    doc_date: str = Form(None),
    received_date: str = Form(None),
    description: str = Form(None),
    keywords: str = Form(None),
    internal_notes: str = Form(None),
    notes: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    if not office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")

    # Permission check
    if not check_user_permission(user, 'documents', 'add'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة مستندات")

    if not name.strip() or len(name) > 250:
        raise HTTPException(status_code=400, detail="اسم المستند مطلوب ولا يتجاوز 250 حرفاً")

    # If case specified, check authorization
    if case_id:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case or not user_can_access_case(db, user, case_id):
            raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة مستندات لهذه القضية")
        if user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0 and case.lead_lawyer_id != user.id:
            raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة مستندات لهذه القضية")
        # Auto-link client if empty
        if not client_id and case.law_clients:
            client_id = case.law_clients[0].id
    if client_id:
        linked_client = db.query(LawClients).filter(
            LawClients.id == client_id,
            LawClients.office_id == office_id,
            LawClients.is_deleted == 0,
        ).first()
        if not linked_client or (case_id and linked_client.case_id and linked_client.case_id != case_id):
            raise HTTPException(status_code=403, detail="الموكل المحدد لا يتبع لمكتبك أو للقضية")

    # Generate or validate unique doc_code
    if not doc_code or not doc_code.strip():
        final_doc_code = generate_document_code(db, office_id)
    else:
        final_doc_code = doc_code.strip()
        # Verify uniqueness within office
        exists = db.query(LawDocuments).filter(
            LawDocuments.office_id == office_id,
            LawDocuments.doc_code == final_doc_code,
            LawDocuments.is_deleted == 0
        ).first()
        if exists:
            final_doc_code = generate_document_code(db, office_id)

    # Secure file processing
    file_path_str = None
    file_size_val = None
    file_type_val = None

    if file and file.filename and "".join(c for c in file.filename if c.isalnum() or c in ' ._-'):
        clean_fn = "".join(c for c in file.filename if c.isalnum() or c in ' ._-')
        ext = clean_fn.split('.')[-1].lower() if '.' in clean_fn else ''
        allowed_exts = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"عذراً، نوع الملف غير مسموح به ({ext})")

        MAX_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
        file_bytes = await file.read(MAX_SIZE_BYTES + 1)
        if len(file_bytes) > MAX_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد الأقصى المسموح به (25 ميجابايت)")

        from core.security import validate_file_signature
        if not validate_file_signature(file_bytes, ext):
            raise HTTPException(status_code=400, detail="فشل التحقق من أمان محتوى الملف. يرجى رفع ملف سليم وصحيح.")

        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(DOCUMENTS_UPLOAD_DIR, filename)
        with open(path, "wb") as f_out:
            f_out.write(file_bytes)

        file_path_str = f"{DOCUMENTS_UPLOAD_DIR}/{filename}"
        file_size_val = len(file_bytes)
        file_type_val = ext

    # Set default received_date to today if not provided
    final_received_date = received_date or datetime.now().strftime("%Y-%m-%d")

    d = LawDocuments(
        office_id=office_id,
        case_id=case_id,
        client_id=client_id,
        name=name.strip(),
        document_type_key=document_type_key,
        doc_code=final_doc_code,
        doc_date=doc_date,
        received_date=final_received_date,
        description=description,
        keywords=keywords,
        internal_notes=internal_notes,
        notes=notes or description,
        file_path=file_path_str,
        file_size=file_size_val,
        file_type=file_type_val,
        is_archived=0,
        created_by_user_id=user.id
    )
    db.add(d)
    db.commit()
    db.refresh(d)

    # Automatic Initial Version Creation (v1.0)
    if file_path_str:
        v1 = LawDocumentVersions(
            document_id=d.id,
            office_id=office_id,
            version_number=1,
            file_path=file_path_str,
            file_size=file_size_val or 0,
            file_type=file_type_val or 'file',
            change_summary="المسودة الأولية (الإصدار الأساسي v1.0)",
            is_current=1,
            uploaded_by_user_id=user.id
        )
        db.add(v1)
        db.commit()

    log_document_audit(db, office_id, user, "إضافة مستند", d, f"النوع: {document_type_key}")
    return RedirectResponse(url="/documents?msg=added", status_code=303)


@router.post("/documents/edit")
async def edit_document(
    request: Request,
    doc_id: int = Form(...),
    name: str = Form(...),
    document_type_key: str = Form(...),
    doc_code: str = Form(None),
    client_id: int = Form(None),
    case_id: int = Form(None),
    doc_date: str = Form(None),
    received_date: str = Form(None),
    description: str = Form(None),
    keywords: str = Form(None),
    internal_notes: str = Form(None),
    notes: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    if not office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")

    d = db.query(LawDocuments).filter(
        LawDocuments.id == doc_id,
        LawDocuments.office_id == office_id,
        LawDocuments.is_deleted == 0
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if not check_user_permission(user, "documents", "edit"):
        raise HTTPException(status_code=403, detail="غير مصرح بتعديل المستندات")

    # RBAC Check: Ensure user has access
    if d.case_id and not user_can_access_case(db, user, d.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل هذا المستند")

    if case_id:
        destination_case = db.query(LawCases).filter(
            LawCases.id == case_id,
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0,
        ).first()
        if not destination_case or not user_can_access_case(db, user, case_id):
            raise HTTPException(status_code=403, detail="القضية المحددة غير موجودة أو غير مصرح بها")
    if client_id:
        linked_client = db.query(LawClients).filter(
            LawClients.id == client_id,
            LawClients.office_id == office_id,
            LawClients.is_deleted == 0,
        ).first()
        if not linked_client or (case_id and linked_client.case_id and linked_client.case_id != case_id):
            raise HTTPException(status_code=403, detail="الموكل المحدد لا يتبع لمكتبك أو للقضية")

    if not name.strip() or len(name) > 250:
        raise HTTPException(status_code=400, detail="اسم المستند غير صالح")

    # Update file if uploaded
    if file and file.filename and "".join(c for c in file.filename if c.isalnum() or c in ' ._-'):
        clean_fn = "".join(c for c in file.filename if c.isalnum() or c in ' ._-')
        ext = clean_fn.split('.')[-1].lower() if '.' in clean_fn else ''
        allowed_exts = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"نوع الملف غير مسموح به ({ext})")

        MAX_SIZE_BYTES = 25 * 1024 * 1024
        file_bytes = await file.read(MAX_SIZE_BYTES + 1)
        if len(file_bytes) > MAX_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد المسموح به")

        from core.security import validate_file_signature
        if not validate_file_signature(file_bytes, ext):
            raise HTTPException(status_code=400, detail="فشل التحقق من أمان محتوى الملف")

        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(DOCUMENTS_UPLOAD_DIR, filename)
        with open(path, "wb") as f_out:
            f_out.write(file_bytes)

        d.file_path = f"{DOCUMENTS_UPLOAD_DIR}/{filename}"
        d.file_size = len(file_bytes)
        d.file_type = ext

        # Auto-track new version on edit file upload
        db.query(LawDocumentVersions).filter(LawDocumentVersions.document_id == d.id).update({"is_current": 0})
        existing_vs = db.query(LawDocumentVersions.version_number).filter(LawDocumentVersions.document_id == d.id).all()
        max_v = max([v[0] for v in existing_vs], default=0)
        next_v = max_v + 1
        new_v = LawDocumentVersions(
            document_id=d.id,
            office_id=office_id,
            version_number=next_v,
            file_path=f"{DOCUMENTS_UPLOAD_DIR}/{filename}",
            file_size=len(file_bytes),
            file_type=ext,
            change_summary=f"تحديث مسودة المستند (إصدار v{next_v}.0)",
            is_current=1,
            uploaded_by_user_id=user.id
        )
        db.add(new_v)

    d.name = name.strip()
    d.document_type_key = document_type_key
    if doc_code and doc_code.strip():
        d.doc_code = doc_code.strip()
    d.case_id = case_id
    d.client_id = client_id
    d.doc_date = doc_date
    d.received_date = received_date
    d.description = description
    d.keywords = keywords
    d.internal_notes = internal_notes
    d.notes = notes or description
    d.updated_by_user_id = user.id

    db.commit()
    log_document_audit(db, office_id, user, "تعديل مستند", d, "تم تحديث بيانات المستند")
    return RedirectResponse(url="/documents?msg=updated", status_code=303)


@router.post("/documents/archive")
async def archive_document(
    request: Request,
    doc_id: int = Form(...),
    action: str = Form("archive"),  # 'archive' or 'restore'
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """Safe archival and restoration of documents - NEVER Hard Delete"""
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    if not office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")

    d = db.query(LawDocuments).filter(
        LawDocuments.id == doc_id,
        LawDocuments.office_id == office_id,
        LawDocuments.is_deleted == 0
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    required_action = "edit" if action == "restore" else "delete"
    if not check_user_permission(user, "documents", required_action):
        raise HTTPException(status_code=403, detail="غير مصرح بهذا الإجراء")
    if d.case_id and not user_can_access_case(db, user, d.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بهذه القضية")

    if action == "restore":
        d.is_archived = 0
        d.archived_at = None
        log_document_audit(db, office_id, user, "استرجاع مستند", d, "تم استرجاع المستند من الأرشيف إلى الحالة النشطة")
        msg = "restored"
    else:
        d.is_archived = 1
        d.archived_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_document_audit(db, office_id, user, "أرشفة مستند", d, "تم نقل المستند إلى الأرشيف بأمان")
        msg = "archived"

    db.commit()
    return RedirectResponse(url=f"/documents?msg={msg}", status_code=303)


@router.get("/api/documents/{doc_id}")
async def get_document_details(
    doc_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """JSON API to fetch full document metadata for View and Edit Modals"""
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    office_id = user.office_id
    d = db.query(LawDocuments).filter(
        LawDocuments.id == doc_id,
        LawDocuments.office_id == office_id,
        LawDocuments.is_deleted == 0
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if not check_user_permission(user, "documents", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بعرض هذا المستند")
    if d.case_id and not user_can_access_case(db, user, d.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بهذه القضية")

    # Authorize internal notes
    can_view_internal = (user.role in ['مدير المكتب', 'المسؤول', 'أدمن', 'محامي', 'محامٍ'])

    # Format file size human readable
    file_size_formatted = ""
    if d.file_size:
        size_kb = d.file_size / 1024
        file_size_formatted = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{(size_kb/1024):.2f} MB"

    return {
        "id": d.id,
        "doc_code": d.doc_code or f"DOC-{d.id}",
        "name": d.name,
        "document_type_key": d.document_type_key,
        "case_id": d.case_id,
        "case_number": d.law_case.case_number if d.law_case else "",
        "case_title": d.law_case.title if d.law_case else "",
        "client_id": d.client_id,
        "client_name": d.law_client.name if d.law_client else (d.law_case.law_clients[0].name if d.law_case and d.law_case.law_clients else ""),
        "doc_date": d.doc_date or "",
        "received_date": d.received_date or "",
        "description": d.description or "",
        "keywords": d.keywords or "",
        "notes": d.notes or "",
        "internal_notes": (d.internal_notes or "") if can_view_internal else "",
        "file_path": (f"/documents/download/{os.path.basename(d.file_path)}" if d.file_path else ""),
        "file_size": d.file_size or 0,
        "file_size_formatted": file_size_formatted,
        "file_type": d.file_type or "",
        "is_archived": d.is_archived or 0,
        "archived_at": d.archived_at or "",
        "created_at": d.created_at or ""
    }


# Secure File Download & Streaming Endpoint
@router.get("/private_uploads/documents/{filename}")
@router.get("/documents/download/{filename}")
async def download_document(
    filename: str,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,10}", filename):
        raise HTTPException(status_code=404, detail="الملف غير موجود")
    if not check_user_permission(user, "documents", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بتنزيل المستندات")

    # Find the document by path
    doc = db.query(LawDocuments).filter(
        ((LawDocuments.file_path == f"private_uploads/documents/{filename}") |
         (LawDocuments.file_path == f"static/uploads/documents/{filename}")),
        LawDocuments.is_deleted == 0,
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود في قاعدة البيانات")

    if doc.office_id != user.office_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا المستند")
    if doc.case_id and not user_can_access_case(db, user, doc.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لمستندات هذه القضية")

    path = os.path.realpath(doc.file_path or "")
    allowed_roots = [
        os.path.realpath(DOCUMENTS_UPLOAD_DIR),
        os.path.realpath(os.path.join("static", "uploads", "documents")),
    ]
    if os.path.basename(path) != filename or not any(
        os.path.commonpath([root, path]) == root for root in allowed_roots
    ) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="الملف غير موجود على الخادم")

    # Log download in audit
    log_document_audit(db, user.office_id, user, "تنزيل مستند", doc, f"الملف: {filename}")

    return FileResponse(path, filename=f"{doc.name}.{doc.file_type or 'pdf'}", headers={"Cache-Control": "private, no-store"})

# ========================================================
# Phase 2: Document Versioning & Historical Drafts System
# ========================================================

@router.get("/api/documents/{doc_id}/versions")
async def get_document_versions(
    doc_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """Return JSON list of all revisions/versions for a document"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")
    doc = db.query(LawDocuments).filter(
        LawDocuments.id == doc_id,
        LawDocuments.office_id == user.office_id,
        LawDocuments.is_deleted == 0
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if doc.case_id and not user_can_access_case(db, user, doc.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول للمستند")

    versions = db.query(LawDocumentVersions).filter(
        LawDocumentVersions.document_id == doc_id
    ).order_by(LawDocumentVersions.version_number.desc()).all()

    v_list = []
    for v in versions:
        up_name = getattr(v.uploader, 'name', None) or getattr(v.uploader, 'username', 'مستخدم النظام')
        v_list.append({
            "id": v.id,
            "version_number": v.version_number,
            "version_tag": f"v{v.version_number}.0",
            "file_type": (v.file_type or 'file').upper(),
            "file_size": v.file_size or 0,
            "change_summary": v.change_summary or ("المسودة الأولية" if v.version_number == 1 else "تعديل مسودة"),
            "is_current": bool(v.is_current),
            "created_at": v.created_at or "-",
            "uploaded_by": up_name,
            "download_url": f"/documents/versions/{v.id}/download"
        })

    return {
        "doc_id": doc.id,
        "doc_name": doc.name,
        "doc_code": doc.doc_code or f"DOC-{doc.id}",
        "total_versions": len(v_list),
        "versions": v_list
    }


@router.post("/documents/{doc_id}/versions/upload")
async def upload_document_version(
    doc_id: int,
    file: UploadFile = File(...),
    change_summary: str = Form(None),
    redirect_to: str = Form("documents"),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """Upload a new version/draft for a document"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if not check_user_permission(user, 'documents', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح لك برفع إصدارات جديدة")

    doc = db.query(LawDocuments).filter(
        LawDocuments.id == doc_id,
        LawDocuments.office_id == user.office_id,
        LawDocuments.is_deleted == 0
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if doc.case_id and not user_can_access_case(db, user, doc.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول")

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="يرجى اختيار ملف صالح للرفع")

    clean_fn = "".join(c for c in file.filename if c.isalnum() or c in ' ._-')
    ext = clean_fn.split('.')[-1].lower() if '.' in clean_fn else ''
    allowed_exts = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"نوع الملف غير مسموح به ({ext})")

    MAX_SIZE_BYTES = 25 * 1024 * 1024
    file_bytes = await file.read(MAX_SIZE_BYTES + 1)
    if len(file_bytes) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد المسموح به (25MB)")

    from core.security import validate_file_signature
    if not validate_file_signature(file_bytes, ext):
        raise HTTPException(status_code=400, detail="فشل التحقق من أمان محتوى الملف")

    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(DOCUMENTS_UPLOAD_DIR, filename)
    with open(path, "wb") as f_out:
        f_out.write(file_bytes)

    # Next version calculation
    existing_v = db.query(LawDocumentVersions.version_number).filter(LawDocumentVersions.document_id == doc.id).all()
    max_v = max([v[0] for v in existing_v], default=0)
    next_v = max_v + 1

    # Demote old versions
    db.query(LawDocumentVersions).filter(LawDocumentVersions.document_id == doc.id).update({"is_current": 0})

    summary_text = change_summary.strip() if change_summary and change_summary.strip() else f"إصدار وتعديل جديد (v{next_v}.0)"
    new_version = LawDocumentVersions(
        document_id=doc.id,
        office_id=user.office_id,
        version_number=next_v,
        file_path=f"{DOCUMENTS_UPLOAD_DIR}/{filename}",
        file_size=len(file_bytes),
        file_type=ext,
        change_summary=summary_text,
        is_current=1,
        uploaded_by_user_id=user.id
    )
    db.add(new_version)

    # Update active document pointer
    doc.file_path = f"{DOCUMENTS_UPLOAD_DIR}/{filename}"
    doc.file_size = len(file_bytes)
    doc.file_type = ext
    doc.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc.updated_by_user_id = user.id

    db.commit()
    log_document_audit(db, user.office_id, user, "رفع إصدار مسودة جديد", doc, f"الإصدار v{next_v}.0: {summary_text}")

    if redirect_to == "case" and doc.case_id:
        return RedirectResponse(url=f"/cases/{doc.case_id}?msg=version_added", status_code=303)
    return RedirectResponse(url="/documents?msg=version_added", status_code=303)


@router.post("/documents/versions/{version_id}/restore")
async def restore_document_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """Revert a document's active state to a past version"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if not check_user_permission(user, 'documents', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح لك باستعادة إصدارات سابقة")

    target_v = db.query(LawDocumentVersions).filter(
        LawDocumentVersions.id == version_id,
        LawDocumentVersions.office_id == user.office_id
    ).first()
    if not target_v:
        raise HTTPException(status_code=404, detail="الإصدار غير موجود")

    doc = db.query(LawDocuments).filter(
        LawDocuments.id == target_v.document_id,
        LawDocuments.office_id == user.office_id,
        LawDocuments.is_deleted == 0
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if doc.case_id and not user_can_access_case(db, user, doc.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول")

    # Demote all versions and set target as current
    db.query(LawDocumentVersions).filter(LawDocumentVersions.document_id == doc.id).update({"is_current": 0})
    target_v.is_current = 1

    doc.file_path = target_v.file_path
    doc.file_size = target_v.file_size
    doc.file_type = target_v.file_type
    doc.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc.updated_by_user_id = user.id

    db.commit()
    log_document_audit(db, user.office_id, user, "استعادة إصدار سابق", doc, f"تمت استعادة المسودة رقم v{target_v.version_number}.0 لتكون النسخة المعتمدة")

    return JSONResponse(content={"success": True, "restored_version": target_v.version_number})


@router.get("/documents/versions/{version_id}/download")
async def download_document_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """Download a specific historical version file"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if not check_user_permission(user, 'documents', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح بتنزيل المستندات")

    target_v = db.query(LawDocumentVersions).filter(
        LawDocumentVersions.id == version_id,
        LawDocumentVersions.office_id == user.office_id
    ).first()
    if not target_v:
        raise HTTPException(status_code=404, detail="الإصدار غير موجود")

    doc = db.query(LawDocuments).filter(
        LawDocuments.id == target_v.document_id,
        LawDocuments.office_id == user.office_id,
        LawDocuments.is_deleted == 0
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if doc.case_id and not user_can_access_case(db, user, doc.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول")

    path = os.path.realpath(target_v.file_path or "")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="الملف غير موجود على الخادم")

    fn_download = f"{doc.name}_v{target_v.version_number}.{target_v.file_type or 'pdf'}"
    log_document_audit(db, user.office_id, user, "تنزيل مسودة إصدار", doc, f"الإصدار v{target_v.version_number}")
    return FileResponse(path, filename=fn_download, headers={"Cache-Control": "private, no-store"})

