from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawPowerOfAttorney
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/power_of_attorney", response_class=HTMLResponse)
async def poa_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        import json
        from datetime import datetime
        office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        records = db.query(LawPowerOfAttorney).filter(LawPowerOfAttorney.office_id == office_id).all()
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "principal_name": r.principal_name,
            "agency_number": r.agency_number, "issue_date": r.issue_date or "",
            "expiry_date": r.expiry_date or "", "notes": r.notes or ""
        } for r in records], ensure_ascii=False)
        today = datetime.now().strftime("%Y-%m-%d")
        return templates.TemplateResponse(request=request, name="power_of_attorney.html", context={
            "user": user, "active_page": "power_of_attorney", "records": records, "cases": cases, "records_json": records_json, "today": today
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

@router.post("/api/poa/save")
async def poa_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        if rec_id:
            r = db.query(LawPowerOfAttorney).filter(LawPowerOfAttorney.id == int(rec_id), LawPowerOfAttorney.office_id == (user.office_id or 1)).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = data.get("case_id")
            r.principal_name = data.get("principal_name")
            r.agency_number = data.get("agency_number")
            r.issue_date = data.get("issue_date") or None
            r.expiry_date = data.get("expiry_date") or None
            r.notes = data.get("notes") or None
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawPowerOfAttorney(
                office_id=user.office_id or 1, case_id=data.get("case_id"),
                principal_name=data.get("principal_name"), agency_number=data.get("agency_number"),
                issue_date=data.get("issue_date") or None, expiry_date=data.get("expiry_date") or None,
                notes=data.get("notes") or None
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": str(e)})

@router.delete("/api/poa/delete/{rec_id}")
async def poa_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawPowerOfAttorney).filter(LawPowerOfAttorney.id == rec_id, LawPowerOfAttorney.office_id == (user.office_id or 1)).first()
    if r: db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف"})

