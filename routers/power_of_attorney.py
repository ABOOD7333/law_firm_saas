from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from datetime import date, datetime, timedelta
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawPowerOfAttorney, LawTasks
from dependencies import get_current_user, templates, check_user_permission, user_can_access_case

router = APIRouter()

@router.get("/power_of_attorney", response_class=HTMLResponse)
async def poa_page(
    request: Request,
    filter_type: str = "all",
    q: str = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not user.office_id:
        raise HTTPException(status_code=403, detail="حسابك غير مرتبط بمكتب")
    if not check_user_permission(user, "power_of_attorney", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بعرض السجلات")

    try:
        import json
        today_str = str(date.today())
        in_30_days = str(date.today() + timedelta(days=30))
        office_id = user.office_id

        cases_query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        cases = cases_query.order_by(LawCases.title.asc()).all()
        records_query = db.query(LawPowerOfAttorney).filter(
            LawPowerOfAttorney.office_id == office_id,
            LawPowerOfAttorney.is_deleted == 0
        )
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            records_query = records_query.filter(LawPowerOfAttorney.case_id.in_([case.id for case in cases]))
        all_records = records_query.order_by(LawPowerOfAttorney.id.desc()).all()

        # Stats calculations
        total_count = len(all_records)
        active_count = sum(1 for r in all_records if r.expiry_date and r.expiry_date >= today_str and getattr(r, 'status', 'active') != 'revoked')
        expiring_soon = sum(1 for r in all_records if r.expiry_date and today_str <= r.expiry_date <= in_30_days and getattr(r, 'status', 'active') != 'revoked')
        expired_count = sum(1 for r in all_records if (r.expiry_date and r.expiry_date < today_str) or getattr(r, 'status', 'active') == 'expired')

        # Filter records
        filtered_records = all_records
        if filter_type == 'active':
            filtered_records = [r for r in filtered_records if r.expiry_date and r.expiry_date >= today_str and getattr(r, 'status', 'active') != 'revoked']
        elif filter_type == 'expiring':
            filtered_records = [r for r in filtered_records if r.expiry_date and today_str <= r.expiry_date <= in_30_days]
        elif filter_type == 'expired':
            filtered_records = [r for r in filtered_records if r.expiry_date and r.expiry_date < today_str]
        elif filter_type == 'litigation':
            filtered_records = [r for r in filtered_records if getattr(r, 'poa_type', '') in ['litigation', 'مرافعة']]

        if q:
            q_lower = q.lower()
            filtered_records = [
                r for r in filtered_records
                if (r.principal_name and q_lower in r.principal_name.lower())
                or (r.agency_number and q_lower in r.agency_number.lower())
                or (getattr(r, 'agent_name', None) and q_lower in r.agent_name.lower())
            ]

        records_json = [{
            "id": r.id,
            "case_id": r.case_id,
            "principal_name": r.principal_name,
            "agent_name": getattr(r, 'agent_name', '') or '',
            "agency_number": r.agency_number,
            "poa_type": getattr(r, 'poa_type', 'litigation') or 'litigation',
            "issuing_authority": getattr(r, 'issuing_authority', '') or '',
            "issue_date": r.issue_date or "",
            "expiry_date": r.expiry_date or "",
            "scope_of_powers": getattr(r, 'scope_of_powers', '') or '',
            "status": getattr(r, 'status', 'active') or 'active',
            "notes": r.notes or ""
        } for r in all_records]

        return templates.TemplateResponse(
            request=request, name="power_of_attorney.html",
            context={
                "user": user,
                "active_page": "power_of_attorney",
                "records": filtered_records,
                "cases": cases,
                "records_json": records_json,
                "today": today_str,
                "filter_type": filter_type,
                "q": q or "",
                "kpis": {
                    "total": total_count,
                    "active": active_count,
                    "expiring": expiring_soon,
                    "expired": expired_count
                }
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="power_of_attorney.py")

@router.get("/api/poa/{rec_id}")
async def poa_get_api(
    rec_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not user.office_id:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    r = db.query(LawPowerOfAttorney).filter(
        LawPowerOfAttorney.id == rec_id,
        LawPowerOfAttorney.office_id == user.office_id,
        LawPowerOfAttorney.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    if not check_user_permission(user, "power_of_attorney", "view") or (r.case_id and not user_can_access_case(db, user, r.case_id)):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    return JSONResponse({
        "ok": True,
        "id": r.id,
        "case_id": r.case_id,
        "principal_name": r.principal_name,
        "agent_name": getattr(r, 'agent_name', '') or '',
        "agency_number": r.agency_number,
        "poa_type": getattr(r, 'poa_type', 'litigation') or 'litigation',
        "issuing_authority": getattr(r, 'issuing_authority', '') or '',
        "issue_date": r.issue_date or "",
        "expiry_date": r.expiry_date or "",
        "scope_of_powers": getattr(r, 'scope_of_powers', '') or '',
        "status": getattr(r, 'status', 'active') or 'active',
        "notes": r.notes or ""
    })

@router.post("/api/poa/save")
async def poa_save(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not user.office_id:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "message": "بيانات الطلب غير صالحة"}, status_code=400)
    data_permission = "edit" if data.get("id") else "add"
    if not check_user_permission(user, "power_of_attorney", data_permission):
        return JSONResponse({"ok": False, "message": "غير مصرح بهذا الإجراء"}, status_code=403)
    rec_id = data.get("id")
    case_id = data.get("case_id")
    try:
        if case_id:
            case = db.query(LawCases).filter(LawCases.id == int(case_id), LawCases.office_id == user.office_id, LawCases.is_deleted == 0).first()
            if not case or not user_can_access_case(db, user, int(case_id)):
                return JSONResponse({"ok": False, "message": "القضية المحددة غير موجودة أو غير مصرح بها"}, status_code=403)

        if rec_id:
            r = db.query(LawPowerOfAttorney).filter(
                LawPowerOfAttorney.id == int(rec_id),
                LawPowerOfAttorney.office_id == user.office_id,
                LawPowerOfAttorney.is_deleted == 0
            ).first()
            if not r:
                return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
            if r.case_id and not user_can_access_case(db, user, r.case_id):
                return JSONResponse({"ok": False, "message": "غير مصرح بهذه القضية"}, status_code=403)
            r.case_id = int(case_id) if case_id else r.case_id
            r.principal_name = data.get("principal_name") or r.principal_name
            r.agent_name = data.get("agent_name")
            r.agency_number = data.get("agency_number") or r.agency_number
            r.poa_type = data.get("poa_type") or "litigation"
            r.issuing_authority = data.get("issuing_authority")
            r.issue_date = data.get("issue_date") or None
            r.expiry_date = data.get("expiry_date") or None
            r.scope_of_powers = data.get("scope_of_powers")
            r.status = data.get("status") or "active"
            r.notes = data.get("notes") or None
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تعديل بيانات الوكالة بنجاح", "id": r.id})
        else:
            new_r = LawPowerOfAttorney(
                office_id=user.office_id,
                case_id=int(case_id) if case_id else None,
                principal_name=data.get("principal_name"),
                agent_name=data.get("agent_name"),
                agency_number=data.get("agency_number") or f"POA-{date.today().year}-01",
                poa_type=data.get("poa_type") or "litigation",
                issuing_authority=data.get("issuing_authority") or "كتابة العدل / منصة ناجز",
                issue_date=data.get("issue_date") or str(date.today()),
                expiry_date=data.get("expiry_date") or None,
                scope_of_powers=data.get("scope_of_powers"),
                status=data.get("status") or "active",
                notes=data.get("notes") or None
            )
            db.add(new_r)
            db.commit()
            db.refresh(new_r)

            # Auto create renewal reminder task before expiry
            if data.get("create_reminder") and new_r.expiry_date:
                t = LawTasks(
                    office_id=user.office_id,
                    case_id=new_r.case_id,
                    title=f"تجديد الوكالة الرسمية #{new_r.agency_number} للموكل {new_r.principal_name}",
                    due_at=new_r.expiry_date,
                    priority_level=1,
                    status_key="pending",
                    task_type="client"
                )
                db.add(t)
                db.commit()

            return JSONResponse({"ok": True, "message": "تمت إضافة الوكالة بنجاح", "id": new_r.id})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": f"حدث خطأ داخلي: {str(e)}"}, status_code=500)

@router.delete("/api/poa/delete/{rec_id}")
async def poa_delete(
    rec_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not user.office_id:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    if not check_user_permission(user, "power_of_attorney", "delete"):
        return JSONResponse({"ok": False, "message": "غير مصرح بالحذف"}, status_code=403)
    r = db.query(LawPowerOfAttorney).filter(
        LawPowerOfAttorney.id == rec_id,
        LawPowerOfAttorney.office_id == user.office_id,
        LawPowerOfAttorney.is_deleted == 0
    ).first()
    if r and r.case_id and not user_can_access_case(db, user, r.case_id):
        return JSONResponse({"ok": False, "message": "غير مصرح بهذه القضية"}, status_code=403)
    if r:
        r.is_deleted = 1
        db.commit()
        return JSONResponse({"ok": True, "message": "تم حذف الوكالة بنجاح"})
    return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
