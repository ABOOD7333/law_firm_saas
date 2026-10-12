from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import date, datetime
import json
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawLimitations, LawTasks
from dependencies import get_current_user, templates

router = APIRouter()

def compute_days_left(due_date_str):
    if not due_date_str:
        return None
    try:
        due = datetime.strptime(str(due_date_str)[:10], "%Y-%m-%d").date()
        today = date.today()
        return (due - today).days
    except Exception:
        return None

@router.get("/limitations", response_class=HTMLResponse)
async def limitations_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        office_id = user.office_id
        cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        ).order_by(LawCases.created_at.desc()).all()

        records = db.query(LawLimitations).filter(
            LawLimitations.office_id == office_id,
            LawLimitations.is_deleted == 0
        ).order_by(LawLimitations.due_date.asc()).all()

        # KPIs and countdown computations
        total_count = len(records)
        active_count = 0
        critical_count = 0
        expired_count = 0
        completed_count = 0

        enhanced_records = []
        for r in records:
            days_left = compute_days_left(r.due_date)
            is_expired = False
            is_urgent = False
            if r.status_key == 'مكتمل':
                completed_count += 1
            elif days_left is not None and days_left < 0:
                is_expired = True
                expired_count += 1
            else:
                active_count += 1
                if (days_left is not None and days_left <= 7) or getattr(r, 'is_critical', 0) == 1:
                    critical_count += 1
                    is_urgent = True

            enhanced_records.append({
                "record": r,
                "days_left": days_left,
                "is_expired": is_expired,
                "is_urgent": is_urgent
            })

        stats = {
            "total": total_count,
            "active": active_count,
            "critical": critical_count,
            "completed": completed_count,
            "expired": expired_count
        }

        records_json = json.dumps([{
            "id": r.id,
            "case_id": r.case_id,
            "case_number": r.law_case.case_number if r.law_case else "",
            "case_title": r.law_case.title if r.law_case else "",
            "title": r.title,
            "limitation_type_key": r.limitation_type_key or "تقادم مدني",
            "status_key": r.status_key or "ساري",
            "start_date": r.start_date or "",
            "due_date": r.due_date or "",
            "days_count": getattr(r, 'days_count', None),
            "action_required": getattr(r, 'action_required', "") or "",
            "alert_days_before": getattr(r, 'alert_days_before', 7) or 7,
            "law_reference": getattr(r, 'law_reference', "") or "",
            "is_critical": getattr(r, 'is_critical', 0) or 0,
            "notes": r.notes or "",
            "days_left": compute_days_left(r.due_date)
        } for r in records], ensure_ascii=False)

        return templates.TemplateResponse(request=request, name="limitations.html", context={
            "user": user,
            "active_page": "limitations",
            "records": enhanced_records,
            "cases": cases,
            "stats": stats,
            "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="limitations.py")

@router.get("/api/limitations/{rec_id}")
async def limitations_get(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawLimitations).filter(
        LawLimitations.id == rec_id,
        LawLimitations.office_id == user.office_id,
        LawLimitations.is_deleted == 0
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
            "limitation_type_key": r.limitation_type_key or "",
            "status_key": r.status_key or "ساري",
            "start_date": r.start_date or "",
            "due_date": r.due_date or "",
            "days_count": getattr(r, 'days_count', None),
            "action_required": getattr(r, 'action_required', "") or "",
            "alert_days_before": getattr(r, 'alert_days_before', 7) or 7,
            "law_reference": getattr(r, 'law_reference', "") or "",
            "is_critical": getattr(r, 'is_critical', 0) or 0,
            "notes": r.notes or "",
            "days_left": compute_days_left(r.due_date)
        }
    })

@router.post("/api/limitations/save")
async def limitations_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        office_id = user.office_id
        rec_id = data.get("id")

        if not data.get("title") or not str(data.get("title")).strip():
            return JSONResponse({"ok": False, "message": "عنوان التنبيه مطلوب"})
        if not data.get("due_date"):
            return JSONResponse({"ok": False, "message": "تاريخ الاستحقاق إلزامي"})

        case_id = data.get("case_id")
        if case_id:
            try:
                case_id = int(case_id)
            except (ValueError, TypeError):
                case_id = None

        days_count = data.get("days_count")
        if days_count:
            try:
                days_count = int(days_count)
            except (ValueError, TypeError):
                days_count = None

        alert_days_before = data.get("alert_days_before")
        if alert_days_before is not None:
            try:
                alert_days_before = int(alert_days_before)
            except (ValueError, TypeError):
                alert_days_before = 7
        else:
            alert_days_before = 7

        is_critical = 1 if data.get("is_critical") in [True, 1, "1", "true"] else 0

        if rec_id:
            r = db.query(LawLimitations).filter(
                LawLimitations.id == int(rec_id),
                LawLimitations.office_id == user.office_id,
                LawLimitations.is_deleted == 0
            ).first()
            if not r:
                return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = case_id
            r.title = str(data.get("title")).strip()
            r.limitation_type_key = data.get("limitation_type_key") or "تقادم مدني"
            r.status_key = data.get("status_key") or "ساري"
            r.start_date = data.get("start_date") or None
            r.due_date = data.get("due_date")
            r.days_count = days_count
            r.action_required = data.get("action_required") or None
            r.alert_days_before = alert_days_before
            r.law_reference = data.get("law_reference") or None
            r.is_critical = is_critical
            r.notes = data.get("notes") or None
            r.updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تحديث تنبيه التقادم بنجاح", "id": r.id})
        else:
            new_r = LawLimitations(
                office_id=office_id,
                case_id=case_id,
                title=str(data.get("title")).strip(),
                limitation_type_key=data.get("limitation_type_key") or "تقادم مدني",
                status_key=data.get("status_key") or "ساري",
                start_date=data.get("start_date") or None,
                due_date=data.get("due_date"),
                days_count=days_count,
                action_required=data.get("action_required") or None,
                alert_days_before=alert_days_before,
                law_reference=data.get("law_reference") or None,
                is_critical=is_critical,
                notes=data.get("notes") or None,
                is_deleted=0
            )
            db.add(new_r)
            db.commit()
            return JSONResponse({"ok": True, "message": "تمت إضافة تنبيه التقادم بنجاح", "id": new_r.id})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": f"حدث خطأ داخلي: {str(e)}"}, status_code=500)

@router.post("/api/limitations/{rec_id}/create-task")
async def limitations_create_task(rec_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawLimitations).filter(
        LawLimitations.id == rec_id,
        LawLimitations.office_id == user.office_id,
        LawLimitations.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "message": "تنبيه التقادم غير موجود"}, status_code=404)

    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass

        task_title = body.get("title") or f"متابعة موعد تقادم: {r.title}"
        action_req = r.action_required or r.notes or "اتخاذ الإجراء القانوني اللازم قبل سقوط الميعاد"
        task_desc = f"تنبيه التقادم: {r.title}\nالاستحقاق: {r.due_date}\nالسند النظامي: {r.law_reference or 'غير محدد'}\nالإجراء المطلوب: {action_req}"

        new_task = LawTasks(
            office_id=user.office_id,
            case_id=r.case_id,
            title=task_title,
            description=task_desc,
            due_at=r.due_date,
            priority_level=1 if getattr(r, 'is_critical', 0) == 1 else 2,
            status_key="pending",
            task_type="إجرائي",
            assignee_user_id=user.id,
            is_deleted=0
        )
        db.add(new_task)
        db.commit()
        return JSONResponse({"ok": True, "message": "تم إنشاء مهمة متابعة بنجاح", "task_id": new_task.id})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": f"فشل إنشاء المهمة: {str(e)}"}, status_code=500)

@router.delete("/api/limitations/delete/{rec_id}")
async def limitations_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawLimitations).filter(
        LawLimitations.id == rec_id,
        LawLimitations.office_id == user.office_id,
        LawLimitations.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "message": "السجل غير موجود"})
    r.is_deleted = 1
    r.updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return JSONResponse({"ok": True, "message": "تم حذف التنبيه بنجاح"})
