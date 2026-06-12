from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawExpenses
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        import json
        office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        records = db.query(LawExpenses).filter(LawExpenses.office_id == office_id).all()
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "title": r.title,
            "amount": r.amount, "expense_at": r.expense_at
        } for r in records], ensure_ascii=False)
        return templates.TemplateResponse(request=request, name="expenses.html", context={
            "user": user, "active_page": "expenses", "records": records, "cases": cases, "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="expenses.py")

@router.post("/api/expenses/save")
async def expenses_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        case_id = data.get("case_id")
        office_id = user.office_id or 1
        
        if case_id:
            # Validate case ownership/office
            case = db.query(LawCases).filter(LawCases.id == int(case_id), LawCases.office_id == office_id).first()
            if not case:
                return JSONResponse({"ok": False, "message": "القضية المحددة غير موجودة أو لا تتبع لمكتبك"})
                
            # Restrict lawyers to their assigned cases if not permitted to view all
            if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0 and case.lead_lawyer_id != user.id:
                return JSONResponse({"ok": False, "message": "غير مصرح لك بإضافة أو تعديل مصاريف لهذه القضية"})
        else:
            return JSONResponse({"ok": False, "message": "يجب تحديد قضية مرتبطة"})

        if rec_id:
            r = db.query(LawExpenses).filter(LawExpenses.id == int(rec_id), LawExpenses.office_id == office_id).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = case_id
            r.title = data.get("title")
            r.amount = data.get("amount", 0)
            r.expense_at = data.get("expense_at")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawExpenses(
                office_id=office_id, case_id=case_id,
                title=data.get("title"), amount=data.get("amount", 0),
                expense_at=data.get("expense_at")
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": str(e)})

@router.delete("/api/expenses/delete/{rec_id}")
async def expenses_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawExpenses).filter(LawExpenses.id == rec_id, LawExpenses.office_id == (user.office_id or 1)).first()
    if r:
        # Check lawyer case visibility permission
        case = db.query(LawCases).filter(LawCases.id == r.case_id).first()
        if case and user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0 and case.lead_lawyer_id != user.id:
            return JSONResponse({"ok": False, "message": "غير مصرح لك بحذف مصاريف هذه القضية"})
        db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف"})

