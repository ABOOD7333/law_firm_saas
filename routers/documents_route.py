from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import traceback
import os
import uuid

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawDocuments

# نستخدم الاستيراد المتأخر لتجنب التكرار (Circular Imports)
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        docs = db.query(LawDocuments).filter(LawDocuments.office_id == (user.office_id or 1)).order_by(LawDocuments.id.desc()).all()
        cases = db.query(LawCases).filter(LawCases.office_id == (user.office_id or 1), LawCases.is_deleted == 0).all()
        return templates.TemplateResponse(request=request, name="documents.html",
            context={"user": user, "docs": docs, "cases": cases, "active_page": "documents"})
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

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
    
    file_path_str = None
    if file and file.filename:
        ext = file.filename.split('.')[-1].lower()
        allowed_exts = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
        if ext not in allowed_exts:
            return HTMLResponse(content=f"<script>alert('عذراً، نوع الملف غير مسموح به ({ext})'); window.history.back();</script>", status_code=400)

        # ── ثغرة DoS: التحقق من حجم الملف قبل الحفظ (حد أقصى 20MB) ──
        MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
        file_bytes = await file.read()
        if len(file_bytes) > MAX_SIZE_BYTES:
            return HTMLResponse(content="<script>alert('حجم الملف يتجاوز الحد المسموح به (20 ميجابايت)'); window.history.back();</script>", status_code=400)

        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join("static", "uploads", "documents", filename)
        with open(path, "wb") as f_out:
            f_out.write(file_bytes)
        file_path_str = f"static/uploads/documents/{filename}"

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
        if file and file.filename:
            ext = file.filename.split('.')[-1].lower()
            allowed_exts = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
            if ext not in allowed_exts:
                return HTMLResponse(content=f"<script>alert('عذراً، نوع الملف غير مسموح به ({ext})'); window.history.back();</script>", status_code=400)

            # ── ثغرة DoS: التحقق من حجم الملف قبل الحفظ (حد أقصى 20MB) ──
            MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
            file_bytes = await file.read()
            if len(file_bytes) > MAX_SIZE_BYTES:
                return HTMLResponse(content="<script>alert('حجم الملف يتجاوز الحد المسموح به (20 ميجابايت)'); window.history.back();</script>", status_code=400)

            filename = f"{uuid.uuid4().hex}.{ext}"
            path = os.path.join("static", "uploads", "documents", filename)
            with open(path, "wb") as f_out:
                f_out.write(file_bytes)
            d.file_path = f"static/uploads/documents/{filename}"

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
    if d: db.delete(d); db.commit()
    return RedirectResponse(url="/documents", status_code=303)

