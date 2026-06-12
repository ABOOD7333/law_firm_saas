from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import traceback
from core.error_handler import safe_error_html
import os
import uuid

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawDocuments

# نستخدم الاستيراد المتأخر لتجنب التكرار (Circular Imports)
from dependencies import get_current_user, templates

router = APIRouter()

# [SECURITY FIX HIGH-02] Ensure private uploads folder exists
os.makedirs("private_uploads/documents", exist_ok=True)


@router.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        docs = db.query(LawDocuments).filter(LawDocuments.office_id == (user.office_id or 1)).order_by(LawDocuments.id.desc()).all()
        cases = db.query(LawCases).filter(LawCases.office_id == (user.office_id or 1), LawCases.is_deleted == 0).all()
        return templates.TemplateResponse(request=request, name="documents.html",
            context={"user": user, "docs": docs, "cases": cases, "active_page": "documents"})
    except Exception as exc:
        return safe_error_html(exc, context="documents_route.py")

@router.post("/documents/add")
async def add_document(
    request: Request,
    case_id: int = Form(...),
    name: str = Form(...),
    document_type_key: str = Form(...),
    doc_date: str = Form(None),
    notes: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id or 1
    
    # IDOR Check: Ensure case belongs to the user's office
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case:
        return HTMLResponse(content="<script>alert('غير مصرح لك بإضافة مستندات لهذه القضية'); window.history.back();</script>", status_code=403)
        
    # RBAC Check: Restrict lawyers to their assigned cases only if they cannot view all
    if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0 and case.lead_lawyer_id != user.id:
        return HTMLResponse(content="<script>alert('غير مصرح لك بإضافة مستندات لهذه القضية'); window.history.back();</script>", status_code=403)
    
    file_path_str = None
    if file and "".join(c for c in file.filename if c.isalnum() or c in ' ._-'):
        ext = "".join(c for c in file.filename if c.isalnum() or c in ' ._-').split('.')[-1].lower()
        allowed_exts = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
        if ext not in allowed_exts:
            return HTMLResponse(content=f"<script>alert('عذراً، نوع الملف غير مسموح به ({ext})'); window.history.back();</script>", status_code=400)

        # ── ثغرة DoS: التحقق من حجم الملف قبل الحفظ (حد أقصى 20MB) ──
        MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
        file_bytes = await file.read()
        if len(file_bytes) > MAX_SIZE_BYTES:
            return HTMLResponse(content="<script>alert('حجم الملف يتجاوز الحد المسموح به (20 ميجابايت)'); window.history.back();</script>", status_code=400)

        # ── ثغرة MIME & Payload: التحقق من التوقيع الرقمي للملف (Magic Bytes) ──
        from core.security import validate_file_signature
        if not validate_file_signature(file_bytes, ext):
            return HTMLResponse(content="<script>alert('فشل التحقق من أمان محتوى الملف. يرجى رفع ملف سليم وصحيح.'); window.history.back();</script>", status_code=400)

        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join("private_uploads", "documents", filename)
        with open(path, "wb") as f_out:
            f_out.write(file_bytes)
        file_path_str = f"private_uploads/documents/{filename}"

    d = LawDocuments(case_id=case_id, office_id=user.office_id or 1,
        name=name, document_type_key=document_type_key,
        doc_date=doc_date, notes=notes, file_path=file_path_str)
    db.add(d); db.commit()
    return RedirectResponse(url="/documents", status_code=303)

@router.post("/documents/edit")
async def edit_document(
    request: Request,
    doc_id: int = Form(...),
    case_id: int = Form(...),
    name: str = Form(...),
    document_type_key: str = Form(...),
    doc_date: str = Form(None),
    notes: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id or 1
    d = db.query(LawDocuments).filter(LawDocuments.id == doc_id, LawDocuments.office_id == office_id).first()
    if d:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
        
        # RBAC Check: Restrict lawyers to their assigned cases only if they cannot view all
        if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0 and case.lead_lawyer_id != user.id:
            return HTMLResponse(content="<script>alert('غير مصرح لك بتعديل مستندات هذه القضية'); window.history.back();</script>", status_code=403)
            
        if file and "".join(c for c in file.filename if c.isalnum() or c in ' ._-'):
            ext = "".join(c for c in file.filename if c.isalnum() or c in ' ._-').split('.')[-1].lower()
            allowed_exts = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
            if ext not in allowed_exts:
                return HTMLResponse(content=f"<script>alert('عذراً، نوع الملف غير مسموح به ({ext})'); window.history.back();</script>", status_code=400)

            # ── ثغرة DoS: التحقق من حجم الملف قبل الحفظ (حد أقصى 20MB) ──
            MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
            file_bytes = await file.read()
            if len(file_bytes) > MAX_SIZE_BYTES:
                return HTMLResponse(content="<script>alert('حجم الملف يتجاوز الحد المسموح به (20 ميجابايت)'); window.history.back();</script>", status_code=400)

            # ── ثغرة MIME & Payload: التحقق من التوقيع الرقمي للملف (Magic Bytes) ──
            from core.security import validate_file_signature
            if not validate_file_signature(file_bytes, ext):
                return HTMLResponse(content="<script>alert('فشل التحقق من أمان محتوى الملف. يرجى رفع ملف سليم وصحيح.'); window.history.back();</script>", status_code=400)

            filename = f"{uuid.uuid4().hex}.{ext}"
            path = os.path.join("private_uploads", "documents", filename)
            with open(path, "wb") as f_out:
                f_out.write(file_bytes)
            d.file_path = f"private_uploads/documents/{filename}"

        d.case_id = case_id
        d.name = name
        d.document_type_key = document_type_key
        d.doc_date = doc_date
        d.notes = notes
        db.commit()
    return RedirectResponse(url="/documents", status_code=303)

@router.post("/documents/delete")
async def delete_document(
    request: Request,
    doc_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    d = db.query(LawDocuments).filter(LawDocuments.id == doc_id, LawDocuments.office_id == (user.office_id or 1)).first()
    if d:
        # RBAC Check: Ensure lawyer owns the case referenced by the document
        case = db.query(LawCases).filter(LawCases.id == d.case_id).first()
        if case and user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0 and case.lead_lawyer_id != user.id:
            return HTMLResponse(content="<script>alert('غير مصرح لك بحذف مستندات هذه القضية'); window.history.back();</script>", status_code=403)
        db.delete(d); db.commit()
    return RedirectResponse(url="/documents", status_code=303)


# [SECURITY FIX HIGH-02] Secure File Access Endpoints
@router.get("/private_uploads/documents/{filename}")
@router.get("/static/uploads/documents/{filename}")
async def download_document(
    filename: str,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    # Find the document in database by file path (either private_uploads or static)
    doc = db.query(LawDocuments).filter(
        (LawDocuments.file_path == f"private_uploads/documents/{filename}") |
        (LawDocuments.file_path == f"static/uploads/documents/{filename}")
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود في قاعدة البيانات")
        
    # Check authorization: must belong to the user's office
    if doc.office_id != user.office_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا المستند")
        
    # RBAC Check: Restrict lawyers to their assigned cases only if they cannot view all
    case = db.query(LawCases).filter(LawCases.id == doc.case_id).first()
    if case and user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0 and case.lead_lawyer_id != user.id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لمستندات هذه القضية")
        
    # Resolve physical path on server
    path = os.path.join("private_uploads", "documents", filename)
    if not os.path.exists(path):
        # Fallback to static uploads for backward compatibility
        path = os.path.join("static", "uploads", "documents", filename)
        
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="الملف غير موجود على الخادم")
        
    return FileResponse(path)

