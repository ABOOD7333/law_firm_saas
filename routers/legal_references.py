from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawLegalReferences
from dependencies import get_current_user, templates

router = APIRouter()

@router.get("/legal_references", response_class=HTMLResponse)
async def legal_references_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        office_id = user.office_id
        cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        ).order_by(LawCases.created_at.desc()).all()

        records = db.query(LawLegalReferences).filter(
            LawLegalReferences.office_id == office_id,
            LawLegalReferences.is_deleted == 0
        ).order_by(LawLegalReferences.created_at.desc()).all()

        # KPIs calculation
        total_count = len(records)
        laws_count = sum(1 for r in records if (r.category or "") == "نظام / قانون")
        precedents_count = sum(1 for r in records if (r.category or "") in ["سابقة قضائية", "مبدأ محكمة عليا"])
        regulations_count = sum(1 for r in records if (r.category or "") in ["لائحة تنفيذية", "تعميم وزاري"])
        linked_cases_count = sum(1 for r in records if r.case_id is not None)

        stats = {
            "total": total_count,
            "laws": laws_count,
            "precedents": precedents_count,
            "regulations": regulations_count,
            "linked_cases": linked_cases_count
        }

        records_json = json.dumps([{
            "id": r.id,
            "case_id": r.case_id,
            "case_number": r.law_case.case_number if r.law_case else "",
            "case_title": r.law_case.title if r.law_case else "",
            "title": r.title,
            "category": r.category or "نظام / قانون",
            "article_number": r.article_number or "",
            "content": r.content or "",
            "keywords": r.keywords or "",
            "source": r.source or "",
            "reference_url": r.reference_url or "",
            "created_at": (r.created_at or "")[:10]
        } for r in records], ensure_ascii=False)

        return templates.TemplateResponse(request=request, name="legal_references.html", context={
            "user": user,
            "active_page": "legal_references",
            "records": records,
            "cases": cases,
            "stats": stats,
            "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="legal_references.py")

@router.get("/api/legal_references/{rec_id}")
async def legal_references_get(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawLegalReferences).filter(
        LawLegalReferences.id == rec_id,
        LawLegalReferences.office_id == user.office_id,
        LawLegalReferences.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)

    return JSONResponse({
        "ok": True,
        "data": {
            "id": r.id,
            "case_id": r.case_id,
            "case_number": r.law_case.case_number if r.law_case else "",
            "title": r.title,
            "category": r.category or "نظام / قانون",
            "article_number": r.article_number or "",
            "content": r.content or "",
            "keywords": r.keywords or "",
            "source": r.source or "",
            "reference_url": r.reference_url or "",
            "created_at": (r.created_at or "")[:10]
        }
    })

@router.post("/api/legal_references/save")
async def legal_references_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        office_id = user.office_id
        rec_id = data.get("id")

        title = str(data.get("title") or "").strip()
        if not title:
            return JSONResponse({"ok": False, "message": "عنوان المرجع القانوني مطلوب"})

        case_id = data.get("case_id")
        if case_id:
            try:
                case_id = int(case_id)
            except (ValueError, TypeError):
                case_id = None

        category = str(data.get("category") or "نظام / قانون").strip()
        article_number = str(data.get("article_number") or "").strip() or None
        content = str(data.get("content") or "").strip() or None
        keywords = str(data.get("keywords") or "").strip() or None
        source = str(data.get("source") or "").strip() or None
        reference_url = str(data.get("reference_url") or "").strip() or None

        if rec_id:
            r = db.query(LawLegalReferences).filter(
                LawLegalReferences.id == int(rec_id),
                LawLegalReferences.office_id == user.office_id,
                LawLegalReferences.is_deleted == 0
            ).first()
            if not r:
                return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = case_id
            r.title = title
            r.category = category
            r.article_number = article_number
            r.content = content
            r.keywords = keywords
            r.source = source
            r.reference_url = reference_url
            r.updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تحديث المرجع القانوني بنجاح", "id": r.id})
        else:
            new_r = LawLegalReferences(
                office_id=office_id,
                case_id=case_id,
                title=title,
                category=category,
                article_number=article_number,
                content=content,
                keywords=keywords,
                source=source,
                reference_url=reference_url,
                is_deleted=0
            )
            db.add(new_r)
            db.commit()
            return JSONResponse({"ok": True, "message": "تمت إضافة المرجع القانوني بنجاح", "id": new_r.id})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": f"حدث خطأ داخلي: {str(e)}"}, status_code=500)

@router.delete("/api/legal_references/delete/{rec_id}")
async def legal_references_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawLegalReferences).filter(
        LawLegalReferences.id == rec_id,
        LawLegalReferences.office_id == user.office_id,
        LawLegalReferences.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "message": "السجل غير موجود"})
    r.is_deleted = 1
    r.updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return JSONResponse({"ok": True, "message": "تم حذف المرجع بنجاح"})
