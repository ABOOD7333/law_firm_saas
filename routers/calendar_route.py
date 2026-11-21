from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from datetime import date, datetime
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawHearings, LawTasks,
    LawLimitations, LawJudgments, LawPowerOfAttorney
)
from dependencies import get_current_user, templates

router = APIRouter()

@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(
    request: Request,
    year: int = None,
    month: int = None,
    event_type: str = "all",
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not user.office_id:
        raise HTTPException(status_code=403, detail="حسابك غير مرتبط بمكتب")

    import calendar as cal_mod
    today = date.today()
    year = year or today.year
    month = month or today.month

    # Clamp month
    if month < 1: month, year = 12, year - 1
    if month > 12: month, year = 1, year + 1

    cal = cal_mod.monthcalendar(year, month)
    month_name = ["", "يناير","فبراير","مارس","أبريل","مايو","يونيو",
                  "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][month]

    month_str = f"{year}-{month:02d}"
    office_id = user.office_id

    # 1. Fetch hearings
    hearings_query = db.query(LawHearings).filter(
        LawHearings.office_id == office_id,
        LawHearings.is_deleted == 0,
        LawHearings.hearing_at.like(f"{month_str}%")
    )

    # 2. Fetch tasks
    tasks_query = db.query(LawTasks).filter(
        LawTasks.office_id == office_id,
        LawTasks.is_deleted == 0,
        LawTasks.due_at.like(f"{month_str}%")
    )

    if user.role in ["محامي", "محامٍ"]:
        visible_case_ids = db.query(LawCases.id).filter(
            LawCases.office_id == office_id,
            LawCases.lead_lawyer_id == user.id,
            LawCases.is_deleted == 0,
        )
        hearings_query = hearings_query.filter(LawHearings.case_id.in_(visible_case_ids))
        tasks_query = tasks_query.filter(
            (LawTasks.assignee_user_id == user.id) |
            (LawTasks.case_id.in_(visible_case_ids))
        )

    hearings = hearings_query.all()
    tasks = tasks_query.all()

    # 3. Fetch limitations / appeal deadlines
    limitations = db.query(LawLimitations).filter(
        LawLimitations.office_id == office_id,
        LawLimitations.is_deleted == 0,
        LawLimitations.due_date.like(f"{month_str}%")
    ).all()

    # 4. Fetch judgments appeal deadlines
    judgments = db.query(LawJudgments).filter(
        LawJudgments.office_id == office_id,
        LawJudgments.is_deleted == 0,
        LawJudgments.appeal_deadline_date.like(f"{month_str}%")
    ).all()

    # 5. Fetch power of attorney expirations
    poas = db.query(LawPowerOfAttorney).filter(
        LawPowerOfAttorney.office_id == office_id,
        LawPowerOfAttorney.is_deleted == 0,
        LawPowerOfAttorney.expiry_date.like(f"{month_str}%")
    ).all()

    # Build events dict keyed by day number
    events = {}
    total_deadlines = len(limitations) + len(judgments)

    if event_type in ["all", "hearings"]:
        for h in hearings:
            try:
                d = int(h.hearing_at[8:10])
                events.setdefault(d, []).append({
                    "id": h.id,
                    "type": "hearing",
                    "title": h.title or "جلسة قضائية",
                    "time": h.hearing_at[11:16] if len(h.hearing_at) > 10 else "",
                    "case_id": h.case_id,
                    "color": "#3b82f6",
                    "icon": "fa-solid fa-gavel"
                })
            except Exception:
                pass

    if event_type in ["all", "tasks"]:
        for t in tasks:
            try:
                d = int(t.due_at[8:10])
                events.setdefault(d, []).append({
                    "id": t.id,
                    "type": "task",
                    "title": t.title or "مهمة عمل",
                    "time": "",
                    "case_id": t.case_id,
                    "color": "#ef4444" if t.priority_level == 1 else "#f59e0b",
                    "icon": "fa-solid fa-list-check"
                })
            except Exception:
                pass

    if event_type in ["all", "deadlines"]:
        for lim in limitations:
            try:
                d = int(lim.due_date[8:10])
                events.setdefault(d, []).append({
                    "id": lim.id,
                    "type": "deadline",
                    "title": f"مهلة تقادم: {lim.title}",
                    "time": "",
                    "case_id": lim.case_id,
                    "color": "#dc2626",
                    "icon": "fa-solid fa-clock-rotate-left"
                })
            except Exception:
                pass

        for j in judgments:
            try:
                if j.appeal_deadline_date:
                    d = int(j.appeal_deadline_date[8:10])
                events.setdefault(d, []).append({
                    "id": j.id,
                    "type": "appeal",
                    "title": f"آخر ميعاد استئناف: صك {j.judgment_number}",
                    "time": "",
                    "case_id": j.case_id,
                    "color": "#9333ea",
                    "icon": "fa-solid fa-scale-balanced"
                })
            except Exception:
                pass

    if event_type in ["all", "poa"]:
        for p in poas:
            try:
                d = int(p.expiry_date[8:10])
                events.setdefault(d, []).append({
                    "id": p.id,
                    "type": "poa",
                    "title": f"انتهاء وكالة: {p.principal_name}",
                    "time": "",
                    "case_id": p.case_id,
                    "color": "#0d9488",
                    "icon": "fa-solid fa-file-signature"
                })
            except Exception:
                pass

    cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).order_by(LawCases.title.asc()).all()

    prev_month = month - 1 if month > 1 else 12
    prev_year  = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year  = year if month < 12 else year + 1

    try:
        return templates.TemplateResponse(
            request=request, name="calendar.html",
            context={
                "user": user,
                "active_page": "calendar",
                "cal": cal,
                "year": year,
                "month": month,
                "month_name": month_name,
                "today": today,
                "events": events,
                "cases": cases,
                "event_type": event_type,
                "prev_month": prev_month,
                "prev_year": prev_year,
                "next_month": next_month,
                "next_year": next_year,
                "total_hearings": len(hearings),
                "total_tasks": len(tasks),
                "total_deadlines": total_deadlines,
                "total_poas": len(poas)
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="calendar_route.py")


@router.get("/api/calendar/events")
async def get_calendar_events_api(
    start: str = None,
    end: str = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not user.office_id:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id

    # Return structured fullcalendar events
    events = []
    hearings = db.query(LawHearings).filter(LawHearings.office_id == office_id, LawHearings.is_deleted == 0).all()
    for h in hearings:
        if h.hearing_at:
            events.append({
                "id": f"hearing-{h.id}",
                "title": f"جلسة: {h.title}",
                "start": h.hearing_at,
                "backgroundColor": "#3b82f6",
                "borderColor": "#1d4ed8",
                "url": f"/hearings/{h.id}" if hasattr(h, 'id') else "/hearings"
            })

    tasks = db.query(LawTasks).filter(LawTasks.office_id == office_id, LawTasks.is_deleted == 0).all()
    for t in tasks:
        if t.due_at:
            events.append({
                "id": f"task-{t.id}",
                "title": f"مهمة: {t.title}",
                "start": t.due_at[:10],
                "backgroundColor": "#ef4444" if t.priority_level == 1 else "#f59e0b",
                "borderColor": "#b45309"
            })

    limitations = db.query(LawLimitations).filter(LawLimitations.office_id == office_id, LawLimitations.is_deleted == 0).all()
    for lim in limitations:
        if lim.due_date:
            events.append({
                "id": f"lim-{lim.id}",
                "title": f"سقوط مهلة: {lim.title}",
                "start": lim.due_date[:10],
                "backgroundColor": "#dc2626",
                "borderColor": "#991b1b"
            })

    return JSONResponse({"ok": True, "events": events})
