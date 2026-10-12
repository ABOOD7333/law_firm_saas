from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawExpenses
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter()

@router.get("/expenses", response_class=HTMLResponse)
async def expenses_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'expenses', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بدخول قسم المصروفات")
    try:
        office_id = user.office_id
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).order_by(LawCases.case_number.asc()).all()
        records = db.query(LawExpenses).filter(
            LawExpenses.office_id == office_id,
            LawExpenses.is_deleted == 0
        ).order_by(LawExpenses.expense_at.desc(), LawExpenses.id.desc()).all()

        current_month = datetime.now().strftime("%Y-%m")
        total_expenses = sum((r.amount or 0.0) for r in records)
        billable_expenses = sum((r.amount or 0.0) for r in records if getattr(r, 'is_billable', 1) == 1)
        non_billable_expenses = total_expenses - billable_expenses
        this_month_expenses = sum((r.amount or 0.0) for r in records if (r.expense_at or "").startswith(current_month))

        stats = {
            "total_expenses": total_expenses,
            "billable_expenses": billable_expenses,
            "non_billable_expenses": non_billable_expenses,
            "this_month_expenses": this_month_expenses,
            "count": len(records)
        }

        records_json = json.dumps([{
            "id": r.id,
            "case_id": r.case_id,
            "case_number": r.law_case.case_number if r.law_case else "",
            "case_title": r.law_case.title if r.law_case else "",
            "title": r.title,
            "amount": r.amount,
            "currency": r.currency or "YER",
            "expense_at": r.expense_at or "",
            "expense_category": getattr(r, 'expense_category', 'رسوم قضائية') or 'رسوم قضائية',
            "is_billable": getattr(r, 'is_billable', 1) or 1,
            "payment_method": getattr(r, 'payment_method', 'تحويل بنكي') or 'تحويل بنكي',
            "notes": getattr(r, 'notes', '') or ""
        } for r in records], ensure_ascii=False)

        return templates.TemplateResponse(request=request, name="expenses.html", context={
            "user": user,
            "active_page": "expenses",
            "records": records,
            "cases": cases,
            "stats": stats,
            "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="expenses.py")

@router.get("/api/expenses/{rec_id}")
async def expenses_get(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    office_id = user.office_id
    r = db.query(LawExpenses).filter(
        LawExpenses.id == rec_id,
        LawExpenses.office_id == office_id,
        LawExpenses.is_deleted == 0
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
            "amount": r.amount,
            "currency": r.currency or "YER",
            "expense_at": r.expense_at or "",
            "expense_category": getattr(r, 'expense_category', 'رسوم قضائية') or 'رسوم قضائية',
            "is_billable": getattr(r, 'is_billable', 1) or 1,
            "payment_method": getattr(r, 'payment_method', 'تحويل بنكي') or 'تحويل بنكي',
            "notes": getattr(r, 'notes', '') or ""
        }
    })

@router.post("/api/expenses/save")
async def expenses_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        case_id = data.get("case_id")
        office_id = user.office_id
        
        if rec_id:
            if not check_user_permission(user, 'expenses', 'edit'):
                return JSONResponse({"ok": False, "message": "غير مصرح لك بتعديل المصاريف"})
        else:
            if not check_user_permission(user, 'expenses', 'add'):
                return JSONResponse({"ok": False, "message": "غير مصرح لك بإضافة مصاريف"})
        
        if case_id:
            case = db.query(LawCases).filter(LawCases.id == int(case_id), LawCases.office_id == office_id, LawCases.is_deleted == 0).first()
            if not case:
                return JSONResponse({"ok": False, "message": "القضية المحددة غير موجودة أو لا تتبع لمكتبك"})
            if user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0 and case.lead_lawyer_id != user.id:
                return JSONResponse({"ok": False, "message": "غير مصرح لك بإضافة أو تعديل مصاريف لهذه القضية"})
        else:
            return JSONResponse({"ok": False, "message": "يجب تحديد قضية مرتبطة بالمصروف"})

        title = str(data.get("title") or "").strip()
        if not title:
            return JSONResponse({"ok": False, "message": "عنوان أو وصف المصروف مطلوب"})

        try:
            amount = float(data.get("amount") or 0.0)
        except (ValueError, TypeError):
            return JSONResponse({"ok": False, "message": "المبلغ المدخل غير صالح"})
            
        if amount <= 0:
            return JSONResponse({"ok": False, "message": "يجب أن يكون مبلغ المصروف أكبر من الصفر"})

        expense_at = data.get("expense_at") or datetime.now().strftime("%Y-%m-%d")
        currency = data.get("currency") or "YER"
        expense_category = data.get("expense_category") or "رسوم قضائية"
        is_billable = 1 if data.get("is_billable") in [1, True, "1", "true"] else 0
        payment_method = data.get("payment_method") or "تحويل بنكي"
        notes = data.get("notes") or None

        if rec_id:
            r = db.query(LawExpenses).filter(
                LawExpenses.id == int(rec_id),
                LawExpenses.office_id == office_id,
                LawExpenses.is_deleted == 0
            ).first()
            if not r:
                return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = int(case_id)
            r.title = title
            r.amount = amount
            r.currency = currency
            r.expense_at = expense_at
            r.expense_category = expense_category
            r.is_billable = is_billable
            r.payment_method = payment_method
            r.notes = notes
            r.updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تحديث المصروف بنجاح", "id": r.id})
        else:
            new_r = LawExpenses(
                office_id=office_id,
                case_id=int(case_id),
                title=title,
                amount=amount,
                currency=currency,
                exchange_rate=1.0,
                expense_at=expense_at,
                expense_category=expense_category,
                is_billable=is_billable,
                payment_method=payment_method,
                notes=notes,
                is_deleted=0
            )
            db.add(new_r)
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تسجيل المصروف بنجاح", "id": new_r.id})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": f"حدث خطأ داخلي: {str(e)}"}, status_code=500)

@router.delete("/api/expenses/delete/{rec_id}")
async def expenses_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    if not check_user_permission(user, 'expenses', 'delete'):
        return JSONResponse({"ok": False, "message": "غير مصرح لك بحذف المصاريف"})
    office_id = user.office_id
    r = db.query(LawExpenses).filter(
        LawExpenses.id == rec_id,
        LawExpenses.office_id == office_id,
        LawExpenses.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "message": "السجل غير موجود"})

    case = db.query(LawCases).filter(LawCases.id == r.case_id).first()
    if case and user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0 and case.lead_lawyer_id != user.id:
        return JSONResponse({"ok": False, "message": "غير مصرح لك بحذف مصاريف هذه القضية"})

    r.is_deleted = 1
    r.updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return JSONResponse({"ok": True, "message": "تم حذف المصروف بنجاح"})
