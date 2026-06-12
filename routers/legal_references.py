from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawLegalReferences
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/legal_references", response_class=HTMLResponse)
async def legal_references_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        import json
        office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        records = db.query(LawLegalReferences).filter(LawLegalReferences.office_id == office_id).all()
        
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "title": r.title, "reference_url": r.reference_url or ""
        } for r in records], ensure_ascii=False)
        
        return templates.TemplateResponse(request=request, name="legal_references.html", context={
            "user": user, "active_page": "legal_references", "records": records, "cases": cases, "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="legal_references.py")

@router.post("/api/legal_references/save")
async def legal_references_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        office_id = user.office_id or 1
        rec_id = data.get("id")
        if rec_id:
            r = db.query(LawLegalReferences).filter(LawLegalReferences.id == int(rec_id), LawLegalReferences.office_id == (user.office_id or 1)).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = data.get("case_id")
            r.title = data.get("title")
            r.reference_url = data.get("reference_url")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawLegalReferences(
                office_id=office_id,
                case_id=data.get("case_id"),
                title=data.get("title"),
                reference_url=data.get("reference_url")
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": str(e)})

@router.delete("/api/legal_references/delete/{rec_id}")
async def legal_references_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawLegalReferences).filter(LawLegalReferences.id == rec_id, LawLegalReferences.office_id == (user.office_id or 1)).first()
    if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
    db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف بنجاح"})
