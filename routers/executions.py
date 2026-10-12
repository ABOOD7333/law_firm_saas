from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from datetime import date
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawExecutions, LawTasks
from dependencies import get_current_user, templates

router = APIRouter()

@router.get("/execution", response_class=HTMLResponse)
async def execution_page(
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

    try:
        import json
        office_id = user.office_id
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).order_by(LawCases.title.asc()).all()

        base_query = db.query(LawExecutions).filter(
            LawExecutions.office_id == office_id,
            LawExecutions.is_deleted == 0
        )
        all_records = base_query.order_by(LawExecutions.id.desc()).all()

        # Stats calculations
        total_count = len(all_records)
        total_claimed = sum(getattr(r, 'claimed_amount', 0.0) or 0.0 for r in all_records)
        total_collected = sum(getattr(r, 'collected_amount', 0.0) or 0.0 for r in all_records)
        active_count = sum(1 for r in all_records if r.status_key in ['active', 'جاري التنفيذ', 'pending', 'قيد الدراسة'])
        completed_count = sum(1 for r in all_records if r.status_key in ['completed', 'تم التنفيذ'])
        recovery_rate = round((total_collected / total_claimed * 100) if total_claimed > 0 else 0, 1)

        # Apply filtering
        filtered_records = all_records
        if filter_type == 'active':
            filtered_records = [r for r in filtered_records if r.status_key in ['active', 'جاري التنفيذ', 'pending', 'قيد الدراسة']]
        elif filter_type == 'completed':
            filtered_records = [r for r in filtered_records if r.status_key in ['completed', 'تم التنفيذ']]
        elif filter_type == 'financial':
            filtered_records = [r for r in filtered_records if getattr(r, 'execution_type', '') in ['financial', 'مالي']]

        if q:
            q_lower = q.lower()
            filtered_records = [
                r for r in filtered_records
                if (r.execution_number and q_lower in r.execution_number.lower())
                or (getattr(r, 'debtor_name', None) and q_lower in r.debtor_name.lower())
                or (r.authority_name and q_lower in r.authority_name.lower())
            ]

        records_json = json.dumps([{
            "id": r.id,
            "case_id": r.case_id,
            "execution_number": r.execution_number,
            "execution_type": getattr(r, 'execution_type', 'financial') or 'financial',
            "debtor_name": getattr(r, 'debtor_name', '') or '',
            "claimed_amount": getattr(r, 'claimed_amount', 0.0) or 0.0,
            "collected_amount": getattr(r, 'collected_amount', 0.0) or 0.0,
            "decision_number": getattr(r, 'decision_number', '') or '',
            "decision_date": getattr(r, 'decision_date', '') or '',
            "authority_name": r.authority_name or "",
            "status_key": r.status_key,
            "request_date": r.request_date or "",
            "notes": getattr(r, 'notes', '') or ""
        } for r in all_records], ensure_ascii=False)

        return templates.TemplateResponse(
            request=request, name="execution.html",
            context={
                "user": user,
                "active_page": "execution",
                "records": filtered_records,
                "cases": cases,
                "records_json": records_json,
                "filter_type": filter_type,
                "q": q or "",
                "kpis": {
                    "total": total_count,
                    "active": active_count,
                    "completed": completed_count,
                    "claimed": total_claimed,
                    "collected": total_collected,
                    "rate": recovery_rate
                }
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="executions.py")

@router.get("/api/executions/{rec_id}")
async def execution_get_api(
    rec_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not user.office_id:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    r = db.query(LawExecutions).filter(
        LawExecutions.id == rec_id,
        LawExecutions.office_id == user.office_id,
        LawExecutions.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return JSONResponse({
        "ok": True,
        "id": r.id,
        "case_id": r.case_id,
        "execution_number": r.execution_number,
        "execution_type": getattr(r, 'execution_type', 'financial') or 'financial',
        "debtor_name": getattr(r, 'debtor_name', '') or '',
        "claimed_amount": getattr(r, 'claimed_amount', 0.0) or 0.0,
        "collected_amount": getattr(r, 'collected_amount', 0.0) or 0.0,
        "decision_number": getattr(r, 'decision_number', '') or '',
        "decision_date": getattr(r, 'decision_date', '') or '',
        "authority_name": r.authority_name or "",
        "status_key": r.status_key,
        "request_date": r.request_date or "",
        "notes": getattr(r, 'notes', '') or ""
    })

@router.post("/api/executions/save")
async def executions_save(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not user.office_id:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        case_id = data.get("case_id")
        if case_id:
            case = db.query(LawCases).filter(LawCases.id == int(case_id), LawCases.office_id == user.office_id).first()
            if not case:
                return JSONResponse({"ok": False, "message": "القضية المحددة غير موجودة أو غير مصرح بها"}, status_code=403)

        if rec_id:
            r = db.query(LawExecutions).filter(
                LawExecutions.id == int(rec_id),
                LawExecutions.office_id == user.office_id,
                LawExecutions.is_deleted == 0
            ).first()
            if not r:
                return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
            r.case_id = int(case_id) if case_id else r.case_id
            r.execution_number = data.get("execution_number") or r.execution_number
            r.authority_name = data.get("authority_name")
            r.execution_type = data.get("execution_type") or "financial"
            r.debtor_name = data.get("debtor_name")
            r.claimed_amount = float(data.get("claimed_amount") or 0.0)
            r.collected_amount = float(data.get("collected_amount") or 0.0)
            r.decision_number = data.get("decision_number")
            r.decision_date = data.get("decision_date") or None
            r.notes = data.get("notes")
            r.status_key = data.get("status_key") or "جاري التنفيذ"
            r.request_date = data.get("request_date") or None
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تعديل إجراء التنفيذ بنجاح", "id": r.id})
        else:
            new_r = LawExecutions(
                office_id=user.office_id,
                case_id=int(case_id) if case_id else None,
                execution_number=data.get("execution_number") or f"EXEC-{date.today().year}-001",
                authority_name=data.get("authority_name") or "محكمة التنفيذ",
                execution_type=data.get("execution_type") or "financial",
                debtor_name=data.get("debtor_name"),
                claimed_amount=float(data.get("claimed_amount") or 0.0),
                collected_amount=float(data.get("collected_amount") or 0.0),
                decision_number=data.get("decision_number"),
                decision_date=data.get("decision_date") or None,
                notes=data.get("notes"),
                status_key=data.get("status_key") or "جاري التنفيذ",
                request_date=data.get("request_date") or str(date.today())
            )
            db.add(new_r)
            db.commit()
            db.refresh(new_r)

            # Auto create follow-up task if requested
            if data.get("create_task"):
                t = LawTasks(
                    office_id=user.office_id,
                    case_id=new_r.case_id,
                    title=f"متابعة ملف التنفيذ #{new_r.execution_number}",
                    due_at=str(date.today()),
                    priority_level=1,
                    status_key="pending",
                    task_type="court"
                )
                db.add(t)
                db.commit()

            return JSONResponse({"ok": True, "message": "تمت إضافة إجراء التنفيذ بنجاح", "id": new_r.id})
    except Exception as e:
        db.rollback()
        import traceback
        return JSONResponse({"ok": False, "message": f"حدث خطأ داخلي: {str(e)}"}, status_code=500)

@router.delete("/api/executions/delete/{rec_id}")
async def executions_delete(
    rec_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not user.office_id:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawExecutions).filter(
        LawExecutions.id == rec_id,
        LawExecutions.office_id == user.office_id,
        LawExecutions.is_deleted == 0
    ).first()
    if r:
        r.is_deleted = 1
        db.commit()
        return JSONResponse({"ok": True, "message": "تم حذف الإجراء بنجاح"})
    return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
