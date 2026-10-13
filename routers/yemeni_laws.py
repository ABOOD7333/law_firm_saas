"""Authenticated catalog for Yemeni laws and regulations."""

import mimetypes
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.security import validate_file_signature
from core.yemeni_laws import (
    ALLOWED_FILE_EXTENSIONS,
    ALLOWED_LAW_TYPES,
    LEGAL_CATEGORIES,
    MAX_DOCUMENT_BYTES,
    extract_legal_text,
    law_excerpt,
)
from database.database import get_db
from database.models import AccessProfiles, YemeniLawDocument
from dependencies import get_current_user

router = APIRouter(prefix="/api/laws", tags=["Yemeni Law Library"])
LEGACY_DATA_ROOT = (Path(__file__).resolve().parents[1] / "rag_engine" / "knowledge_data").resolve()


def _require_editor(user: AccessProfiles) -> None:
    editor_roles = {
        "صاحب المكتب", "صاحب مكتب", "مدير المكتب", "مدير مكتب", "مدير", "مدير النظام"
    }
    if not user or (getattr(user, "is_superadmin", 0) != 1 and user.role not in editor_roles):
        raise HTTPException(status_code=403, detail="تعديل مكتبة القوانين متاح لإدارة المنصة فقط")


def _serialize(law: YemeniLawDocument, query: str = "", include_text: bool = False) -> dict:
    return {
        "id": law.id,
        "title": law.title,
        "law_type": law.law_type,
        "category": law.category,
        "category_name": LEGAL_CATEGORIES.get(law.category, "قوانين ولوائح يمنية أخرى"),
        "law_number": law.law_number or "",
        "issue_year": law.issue_year or "",
        "source_reference": law.source_reference or "",
        "excerpt": law_excerpt(law.legal_text, query),
        "legal_text": law.legal_text if include_text else None,
        "has_file": bool(law.file_data or law.legacy_file_path),
        "file_name": law.file_name or "",
        "file_type": law.file_type or "",
        "created_at": law.created_at,
        "updated_at": law.updated_at,
    }


@router.get("")
async def list_laws(
    q: str = "",
    category: str = "",
    law_type: str = "",
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    query = db.query(YemeniLawDocument).filter(YemeniLawDocument.is_deleted == 0)
    if category:
        if category not in LEGAL_CATEGORIES:
            raise HTTPException(status_code=400, detail="تصنيف القانون غير صالح")
        query = query.filter(YemeniLawDocument.category == category)
    if law_type:
        if law_type not in ALLOWED_LAW_TYPES:
            raise HTTPException(status_code=400, detail="نوع التشريع غير صالح")
        query = query.filter(YemeniLawDocument.law_type == law_type)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(
            YemeniLawDocument.title.ilike(term),
            YemeniLawDocument.law_number.ilike(term),
            YemeniLawDocument.issue_year.ilike(term),
            YemeniLawDocument.source_reference.ilike(term),
            YemeniLawDocument.legal_text.ilike(term),
        ))
    laws = query.order_by(YemeniLawDocument.title.asc()).limit(500).all()
    return {"success": True, "data": [_serialize(law, q) for law in laws]}


@router.get("/{law_id}")
async def get_law(
    law_id: int,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    law = db.query(YemeniLawDocument).filter(
        YemeniLawDocument.id == law_id, YemeniLawDocument.is_deleted == 0
    ).first()
    if not law:
        raise HTTPException(status_code=404, detail="القانون غير موجود")
    return {"success": True, "data": _serialize(law, include_text=True)}


async def _read_upload(file: UploadFile | None) -> tuple[bytes | None, str | None, str | None, str]:
    if not file or not file.filename:
        return None, None, None, ""
    filename = os.path.basename(file.filename).replace("\x00", "")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="الصيغ المسموحة: PDF وWord DOCX وTXT")
    data = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="حجم المستند يتجاوز 25 ميغابايت")
    if not validate_file_signature(data, extension.lstrip(".")):
        raise HTTPException(status_code=400, detail="محتوى الملف لا يطابق امتداده")
    extracted = extract_legal_text(data, extension)
    return data, filename, extension.lstrip("."), extracted


def _validate_fields(title: str, category: str, law_type: str) -> None:
    if not title.strip() or len(title.strip()) > 300:
        raise HTTPException(status_code=400, detail="أدخل عنواناً واضحاً لا يتجاوز 300 حرف")
    if category not in LEGAL_CATEGORIES:
        raise HTTPException(status_code=400, detail="اختر تصنيفاً من تصنيفات القوانين اليمنية")
    if law_type not in ALLOWED_LAW_TYPES:
        raise HTTPException(status_code=400, detail="نوع التشريع يجب أن يكون قانوناً أو لائحة")


@router.post("")
async def add_law(
    title: str = Form(...),
    category: str = Form(...),
    law_type: str = Form("law"),
    law_number: str = Form(""),
    issue_year: str = Form(""),
    source_reference: str = Form(""),
    legal_text: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    _require_editor(current_user)
    _validate_fields(title, category, law_type)
    file_data, file_name, file_type, extracted = await _read_upload(file)
    content = legal_text.strip() or extracted
    if not content and not file_data:
        raise HTTPException(status_code=400, detail="أدخل نص القانون أو ارفع مستنده")
    law = YemeniLawDocument(
        title=title.strip(), law_type=law_type, category=category,
        law_number=law_number.strip() or None, issue_year=issue_year.strip() or None,
        source_reference=source_reference.strip() or None, legal_text=content,
        file_name=file_name, file_type=file_type, file_data=file_data,
        uploaded_by=current_user.id,
    )
    db.add(law)
    db.commit()
    db.refresh(law)
    return {"success": True, "data": _serialize(law, include_text=True)}


@router.post("/{law_id}")
async def update_law(
    law_id: int,
    title: str = Form(...),
    category: str = Form(...),
    law_type: str = Form("law"),
    law_number: str = Form(""),
    issue_year: str = Form(""),
    source_reference: str = Form(""),
    legal_text: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    _require_editor(current_user)
    _validate_fields(title, category, law_type)
    law = db.query(YemeniLawDocument).filter(
        YemeniLawDocument.id == law_id, YemeniLawDocument.is_deleted == 0
    ).first()
    if not law:
        raise HTTPException(status_code=404, detail="القانون غير موجود")
    file_data, file_name, file_type, extracted = await _read_upload(file)
    law.title = title.strip()
    law.category = category
    law.law_type = law_type
    law.law_number = law_number.strip() or None
    law.issue_year = issue_year.strip() or None
    law.source_reference = source_reference.strip() or None
    if legal_text.strip():
        law.legal_text = legal_text.strip()
    elif extracted:
        law.legal_text = extracted
    if file_data is not None:
        law.file_data = file_data
        law.file_name = file_name
        law.file_type = file_type
        law.legacy_file_path = None
    law.updated_at = datetime.utcnow().isoformat(timespec="seconds")
    db.commit()
    db.refresh(law)
    return {"success": True, "data": _serialize(law, include_text=True)}


@router.delete("/{law_id}")
async def delete_law(
    law_id: int,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    _require_editor(current_user)
    law = db.query(YemeniLawDocument).filter(
        YemeniLawDocument.id == law_id, YemeniLawDocument.is_deleted == 0
    ).first()
    if not law:
        raise HTTPException(status_code=404, detail="القانون غير موجود")
    law.is_deleted = 1
    law.updated_at = datetime.utcnow().isoformat(timespec="seconds")
    db.commit()
    return {"success": True}


@router.get("/{law_id}/download")
async def download_law(
    law_id: int,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    law = db.query(YemeniLawDocument).filter(
        YemeniLawDocument.id == law_id, YemeniLawDocument.is_deleted == 0
    ).first()
    if not law:
        raise HTTPException(status_code=404, detail="القانون غير موجود")

    if law.file_data:
        filename = law.file_name or f"{law.title}.{law.file_type or 'pdf'}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body = law.file_data
    elif law.legacy_file_path:
        legacy_path = Path(law.legacy_file_path).resolve()
        if not legacy_path.is_relative_to(LEGACY_DATA_ROOT) or not legacy_path.is_file():
            body = None
        else:
            body = legacy_path.read_bytes()
        filename = law.file_name or f"{law.title}.txt"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    else:
        body = law.legal_text.encode("utf-8")
        filename = f"{law.title}.txt"
        content_type = "text/plain; charset=utf-8"

    if body is None:
        raise HTTPException(status_code=404, detail="ملف هذا التشريع غير متاح؛ يمكن تنزيل النص المحفوظ بدلاً منه")
    safe_header = quote(filename, safe="")
    return Response(
        content=body,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_header}"},
    )
