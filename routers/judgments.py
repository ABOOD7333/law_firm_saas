import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session

from core.error_handler import safe_error_html
from database.database import get_db
from database.models import AccessProfiles, LawCases, LawJudgments, LawTasks, LawExecutions, LawOffices
from dependencies import get_current_user, templates, check_user_permission, user_can_access_case
from core.upload_security import save_upload

router = APIRouter(tags=["Judgments & Court Decrees"])


@router.get("/judgments", response_class=HTMLResponse)
async def judgments_page(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "judgments", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بعرض الأحكام")
    try:
        office_id = user.office_id

        # 1. Fetch judgments for office (exclude soft-deleted)
        case_query = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        )
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            case_query = case_query.filter(LawCases.lead_lawyer_id == user.id)
        cases = case_query.order_by(LawCases.id.desc()).all()
        visible_case_ids = [case.id for case in cases]

        judgment_query = db.query(LawJudgments).filter(
            LawJudgments.office_id == office_id,
            LawJudgments.is_deleted == 0
        )
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            judgment_query = judgment_query.filter(
                LawJudgments.case_id.in_(visible_case_ids) if visible_case_ids else LawJudgments.case_id == -1
            )
        raw_judgments = judgment_query.order_by(LawJudgments.judgment_date.desc()).all()

        # 3. Serialized cases for quick dynamic autofill in modals
        cases_json = []
        for c in cases:
            client_name = c.law_clients[0].name if c.law_clients else "غير محدد"
            cases_json.append({
                "id": c.id,
                "case_number": c.case_number or "",
                "title": c.title or "",
                "court_name": getattr(c, "court_name", "") or "",
                "case_type": getattr(c, "case_type_key", "") or "",
                "client_name": client_name
            })

        # 4. Process each judgment with dynamic appeal deadline countdown
        today_date = datetime.now().date()
        processed_judgments = []
        for j in raw_judgments:
            days_left = None
            deadline_status = "none" # none, active_safe, active_warning, active_urgent, expired, final

            if j.is_final == 1:
                deadline_status = "final"
            elif j.appeal_deadline_date:
                try:
                    deadline_dt = datetime.strptime(j.appeal_deadline_date, "%Y-%m-%d").date()
                    delta = (deadline_dt - today_date).days
                    days_left = delta
                    if delta < 0:
                        deadline_status = "expired"
                    elif delta <= 7:
                        deadline_status = "active_urgent"
                    elif delta <= 14:
                        deadline_status = "active_warning"
                    else:
                        deadline_status = "active_safe"
                except Exception:
                    deadline_status = "none"

            j.days_left = days_left
            j.deadline_status = deadline_status
            processed_judgments.append(j)

        # 5. Advanced KPIs
        total_judgments = len(processed_judgments)
        won_judgments = sum(1 for j in processed_judgments if j.status_key in ['صدر لصالحنا', 'لصالح الموكل'])
        lost_judgments = sum(1 for j in processed_judgments if j.status_key in ['صدر ضدنا', 'ضد الموكل'])
        total_awarded_amount = sum((j.awarded_amount or 0.0) for j in processed_judgments if j.status_key in ['صدر لصالحنا', 'لصالح الموكل'])
        under_appeal_count = sum(1 for j in processed_judgments if j.deadline_status in ['active_safe', 'active_warning', 'active_urgent'])
        final_count = sum(1 for j in processed_judgments if j.is_final == 1)

        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()

        return templates.TemplateResponse(
            request=request,
            name="judgments.html",
            context={
                "user": user,
                "office": office,
                "judgments": processed_judgments,
                "cases": cases,
                "cases_json": cases_json,
                "total_judgments": total_judgments,
                "won_judgments": won_judgments,
                "lost_judgments": lost_judgments,
                "total_awarded_amount": total_awarded_amount,
                "under_appeal_count": under_appeal_count,
                "final_count": final_count,
                "active_page": "judgments"
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="judgments.py")


@router.post("/judgments/add")
async def add_judgment(
    request: Request,
    case_id: int = Form(...),
    judgment_date: str = Form(...),
    court_name: Optional[str] = Form(None),
    chamber_name: Optional[str] = Form(None),
    judge_name: Optional[str] = Form(None),
    decree_number: Optional[str] = Form(None),
    litigation_degree: Optional[str] = Form("ابتدائي"),
    judgment_type: Optional[str] = Form("موضوعي"),
    status_key: Optional[str] = Form("صدر لصالحنا"),
    judgment_text: Optional[str] = Form(None),
    notification_date: Optional[str] = Form(None),
    appeal_deadline_days: int = Form(30),
    awarded_amount: float = Form(0.0),
    legal_fees_awarded: float = Form(0.0),
    is_final: int = Form(0),
    generate_appeal_task: Optional[str] = Form(None),
    redirect_to: Optional[str] = Form(None),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "judgments", "add"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتسجيل أحكام")

    office_id = user.office_id
    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0
    ).first()
    if not case or not user_can_access_case(db, user, case_id):
        raise HTTPException(status_code=404, detail="القضية غير موجودة أو غير مصرح بها")

    # Compute appeal deadline date
    appeal_deadline_date = None
    if notification_date and notification_date.strip():
        try:
            notif_dt = datetime.strptime(notification_date.strip(), "%Y-%m-%d").date()
            appeal_deadline_date = (notif_dt + timedelta(days=appeal_deadline_days)).strftime("%Y-%m-%d")
        except Exception:
            pass

    # Handle file attachment
    attachment_path = None
    if attachment and attachment.filename:
        upload_dir = os.path.join("static", "uploads", "judgments")
        safe_filename = save_upload(attachment, upload_dir)
        attachment_path = f"/static/uploads/judgments/{safe_filename}"

    new_judgment = LawJudgments(
        case_id=case_id,
        office_id=office_id,
        judgment_date=judgment_date.strip(),
        court_name=court_name.strip() if court_name else (case.court_name or ""),
        chamber_name=chamber_name.strip() if chamber_name else "",
        judge_name=judge_name.strip() if judge_name else "",
        decree_number=decree_number.strip() if decree_number else "",
        litigation_degree=litigation_degree.strip() if litigation_degree else "ابتدائي",
        judgment_type=judgment_type.strip() if judgment_type else "موضوعي",
        status_key=status_key.strip() if status_key else "صدر الحكم",
        judgment_text=judgment_text.strip() if judgment_text else "",
        notification_date=notification_date.strip() if notification_date else None,
        appeal_deadline_days=appeal_deadline_days,
        appeal_deadline_date=appeal_deadline_date,
        awarded_amount=awarded_amount,
        legal_fees_awarded=legal_fees_awarded,
        is_final=is_final,
        attachment_path=attachment_path,
        is_deleted=0
    )
    db.add(new_judgment)
    db.flush()

    # Generate automated appeal task if requested
    if generate_appeal_task == "1" and appeal_deadline_date and is_final == 0:
        task_title = f"إعداد لائحة اعتراضية واستئناف لحكم صك ({decree_number or new_judgment.id}) - قضية {case.case_number}"
        appeal_task = LawTasks(
            case_id=case.id,
            office_id=office_id,
            assignee_user_id=case.lead_lawyer_id or user.id,
            title=task_title[:200],
            description=f"مهمة استئناف تلقائية ناتجة عن تسجيل حكم قضائي صادر بتاريخ {judgment_date}. تنتهي مهلة الاستئناف النظامية بتاريخ {appeal_deadline_date}.",
            due_at=f"{appeal_deadline_date} 12:00:00",
            status_key="pending",
            priority_level=3,
            is_active=1,
            is_deleted=0
        )
        db.add(appeal_task)

    db.commit()

    target = f"/cases/{case_id}" if redirect_to == "case" else "/judgments"
    return RedirectResponse(url=target, status_code=303)


@router.post("/judgments/edit")
async def edit_judgment(
    request: Request,
    judgment_id: int = Form(...),
    case_id: int = Form(...),
    judgment_date: str = Form(...),
    court_name: Optional[str] = Form(None),
    chamber_name: Optional[str] = Form(None),
    judge_name: Optional[str] = Form(None),
    decree_number: Optional[str] = Form(None),
    litigation_degree: Optional[str] = Form("ابتدائي"),
    judgment_type: Optional[str] = Form("موضوعي"),
    status_key: Optional[str] = Form("صدر لصالحنا"),
    judgment_text: Optional[str] = Form(None),
    notification_date: Optional[str] = Form(None),
    appeal_deadline_days: int = Form(30),
    awarded_amount: float = Form(0.0),
    legal_fees_awarded: float = Form(0.0),
    is_final: int = Form(0),
    redirect_to: Optional[str] = Form(None),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "judgments", "edit"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل الأحكام")

    office_id = user.office_id
    j = db.query(LawJudgments).filter(
        LawJudgments.id == judgment_id,
        LawJudgments.office_id == office_id,
        LawJudgments.is_deleted == 0
    ).first()
    if not j:
        raise HTTPException(status_code=404, detail="الحكم غير موجود")
    if not user_can_access_case(db, user, j.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بهذا الحكم")
    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0,
    ).first()
    if not case or not user_can_access_case(db, user, case_id):
        raise HTTPException(status_code=403, detail="القضية المحددة غير موجودة أو غير مصرح بها")

    # Recompute appeal deadline date
    appeal_deadline_date = None
    if notification_date and notification_date.strip():
        try:
            notif_dt = datetime.strptime(notification_date.strip(), "%Y-%m-%d").date()
            appeal_deadline_date = (notif_dt + timedelta(days=appeal_deadline_days)).strftime("%Y-%m-%d")
        except Exception:
            pass

    j.case_id = case_id
    j.judgment_date = judgment_date.strip()
    j.court_name = court_name.strip() if court_name else j.court_name
    j.chamber_name = chamber_name.strip() if chamber_name else j.chamber_name
    j.judge_name = judge_name.strip() if judge_name else j.judge_name
    j.decree_number = decree_number.strip() if decree_number else j.decree_number
    j.litigation_degree = litigation_degree.strip() if litigation_degree else j.litigation_degree
    j.judgment_type = judgment_type.strip() if judgment_type else j.judgment_type
    j.status_key = status_key.strip() if status_key else j.status_key
    j.judgment_text = judgment_text.strip() if judgment_text else ""
    j.notification_date = notification_date.strip() if notification_date else None
    j.appeal_deadline_days = appeal_deadline_days
    j.appeal_deadline_date = appeal_deadline_date
    j.awarded_amount = awarded_amount
    j.legal_fees_awarded = legal_fees_awarded
    j.is_final = is_final
    j.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Handle file replacement
    if attachment and attachment.filename:
        upload_dir = os.path.join("static", "uploads", "judgments")
        safe_filename = save_upload(attachment, upload_dir)
        j.attachment_path = f"/static/uploads/judgments/{safe_filename}"

    db.commit()

    target = redirect_to if redirect_to else "/judgments"
    return RedirectResponse(url=target, status_code=303)


@router.post("/judgments/delete")
async def delete_judgment(
    request: Request,
    judgment_id: int = Form(...),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "judgments", "delete"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف الأحكام")

    office_id = user.office_id
    j = db.query(LawJudgments).filter(
        LawJudgments.id == judgment_id,
        LawJudgments.office_id == office_id,
        LawJudgments.is_deleted == 0
    ).first()
    if j:
        if not user_can_access_case(db, user, j.case_id):
            raise HTTPException(status_code=403, detail="غير مصرح بهذا الحكم")
        j.is_deleted = 1
        db.commit()

    target = f"/cases/{j.case_id}" if redirect_to == "case" and j else "/judgments"
    return RedirectResponse(url=target, status_code=303)


@router.post("/judgments/{judgment_id}/convert-to-execution")
async def convert_judgment_to_execution(
    judgment_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """تحويل الحكم القطعي الصادر لصالح الموكل مباشرة إلى ملف وسند تنفيذي"""
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if not check_user_permission(user, "judgments", "edit") or not check_user_permission(user, "execution", "add"):
        raise HTTPException(status_code=403, detail="غير مصرح بإنشاء ملف التنفيذ")

    office_id = user.office_id
    j = db.query(LawJudgments).filter(
        LawJudgments.id == judgment_id,
        LawJudgments.office_id == office_id,
        LawJudgments.is_deleted == 0
    ).first()
    if not j:
        raise HTTPException(status_code=404, detail="الحكم غير موجود")
    if not user_can_access_case(db, user, j.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بهذا الحكم")

    today_str = datetime.now().strftime("%Y-%m-%d")
    exec_num = f"EXEC-{j.decree_number or j.id}-{int(datetime.now().timestamp()) % 10000}"

    new_execution = LawExecutions(
        case_id=j.case_id,
        office_id=office_id,
        execution_number=exec_num,
        authority_name="محكمة التنفيذ",
        status_key="قيد تقديم الطلب",
        request_date=today_str,
        is_deleted=0
    )
    db.add(new_execution)
    j.is_final = 1
    db.commit()

    return JSONResponse({
        "success": True,
        "message": f"تم إنشاء ملف تنفيذ بنجاح برقم {exec_num}",
        "execution_id": new_execution.id
    })


@router.get("/judgments/{judgment_id}/attachment")
async def download_judgment_attachment(
    judgment_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
):
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if not check_user_permission(user, "judgments", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بتنزيل الحكم")
    judgment = db.query(LawJudgments).filter(
        LawJudgments.id == judgment_id,
        LawJudgments.office_id == user.office_id,
        LawJudgments.is_deleted == 0,
    ).first()
    if not judgment or not judgment.attachment_path:
        raise HTTPException(status_code=404, detail="ملف الحكم غير موجود")
    if not user_can_access_case(db, user, judgment.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بهذا الحكم")
    root = os.path.realpath(os.path.join("static", "uploads", "judgments"))
    path = os.path.realpath(judgment.attachment_path.lstrip("/"))
    if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="الملف غير موجود")
    return FileResponse(path, filename=os.path.basename(path), headers={"Cache-Control": "private, no-store"})


@router.get("/api/judgments/{judgment_id}")
async def get_judgment_json(
    judgment_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")

    if not check_user_permission(user, "judgments", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بعرض الأحكام")
    j = db.query(LawJudgments).filter(
        LawJudgments.id == judgment_id,
        LawJudgments.office_id == user.office_id,
        LawJudgments.is_deleted == 0
    ).first()
    if not j:
        raise HTTPException(status_code=404, detail="الحكم غير موجود")
    if not user_can_access_case(db, user, j.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بهذا الحكم")

    case = j.law_case
    client_name = case.law_clients[0].name if case and case.law_clients else "غير محدد"

    return JSONResponse({
        "id": j.id,
        "case_id": j.case_id,
        "case_title": case.title if case else "",
        "case_number": case.case_number if case else "",
        "client_name": client_name,
        "judgment_date": j.judgment_date,
        "court_name": j.court_name or "",
        "chamber_name": j.chamber_name or "",
        "judge_name": j.judge_name or "",
        "decree_number": j.decree_number or "",
        "litigation_degree": j.litigation_degree or "ابتدائي",
        "judgment_type": j.judgment_type or "موضوعي",
        "status_key": j.status_key or "صدر الحكم",
        "judgment_text": j.judgment_text or "",
        "notification_date": j.notification_date or "",
        "appeal_deadline_days": j.appeal_deadline_days or 30,
        "appeal_deadline_date": j.appeal_deadline_date or "",
        "awarded_amount": float(j.awarded_amount or 0.0),
        "legal_fees_awarded": float(j.legal_fees_awarded or 0.0),
        "is_final": j.is_final or 0,
        "attachment_path": f"/judgments/{j.id}/attachment" if j.attachment_path else ""
    })