from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawLimitations
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/limitations", response_class=HTMLResponse)
async def limitations_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        import json
        office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        records = db.query(LawLimitations).filter(LawLimitations.office_id == office_id).all()
        
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "title": r.title,
            "limitation_type_key": r.limitation_type_key, "status_key": r.status_key,
            "start_date": r.start_date or "", "due_date": r.due_date, "notes": r.notes or ""
        } for r in records], ensure_ascii=False)
        
        return templates.TemplateResponse(request=request, name="limitations.html", context={
            "user": user, "active_page": "limitations", "records": records, "cases": cases, "records_json": records_json
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

@router.post("/api/limitations/save")
async def limitations_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        office_id = user.office_id or 1
        rec_id = data.get("id")
        
        if not data.get("due_date"):
            return JSONResponse({"ok": False, "message": "تاريخ الاستحقاق إلزامي"})

        if rec_id:
            r = db.query(LawLimitations).filter(LawLimitations.id == int(rec_id)).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = data.get("case_id")
            r.title = data.get("title")
            r.limitation_type_key = data.get("limitation_type_key")
            r.status_key = data.get("status_key")
            r.start_date = data.get("start_date") or None
            r.due_date = data.get("due_date")
            r.notes = data.get("notes")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawLimitations(
                office_id=office_id,
                case_id=data.get("case_id"),
                title=data.get("title"),
                limitation_type_key=data.get("limitation_type_key"),
                status_key=data.get("status_key"),
                start_date=data.get("start_date") or None,
                due_date=data.get("due_date"),
                notes=data.get("notes")
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": str(e)})

@router.delete("/api/limitations/delete/{rec_id}")
async def limitations_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawLimitations).filter(LawLimitations.id == rec_id).first()
    if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
    db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف بنجاح"})


