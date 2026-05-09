from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawHearings, LawTasks
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(
    request: Request,
    year: int = None,
    month: int = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    import calendar as cal_mod
    from datetime import date
    today = date.today()
    year  = year  or today.year
    month = month or today.month

    # Clamp month
    if month < 1: month, year = 12, year - 1
    if month > 12: month, year = 1, year + 1

    # Build calendar grid
    cal = cal_mod.monthcalendar(year, month)
    month_name = ["", "يناير","فبراير","مارس","أبريل","مايو","يونيو",
                  "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][month]

    # Fetch hearings this month
    month_str = f"{year}-{month:02d}"
    hearings = db.query(LawHearings).filter(
        LawHearings.hearing_at.like(f"{month_str}%")
    ).all()
    tasks = db.query(LawTasks).filter(
        LawTasks.due_at.like(f"{month_str}%"),
        LawTasks.status_key != "completed"
    ).all()

    # Build events dict keyed by day number
    events = {}
    for h in hearings:
        try:
            d = int(h.hearing_at[8:10])
            events.setdefault(d, []).append({
                "type": "hearing", "title": h.title,
                "time": h.hearing_at[11:16] if len(h.hearing_at) > 10 else "",
                "case_id": h.case_id,
                "color": "#3b82f6"
            })
        except Exception:
            pass
    for t in tasks:
        try:
            d = int(t.due_at[8:10])
            events.setdefault(d, []).append({
                "type": "task", "title": t.title,
                "time": "",
                "color": "#f59e0b" if t.priority_level == 2 else ("#ef4444" if t.priority_level == 1 else "#10b981")
            })
        except Exception:
            pass

    # Prev / next month
    prev_month = month - 1 if month > 1 else 12
    prev_year  = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year  = year if month < 12 else year + 1

    try:
        return templates.TemplateResponse(request=request, name="calendar.html",
            context={"user": user, "active_page": "calendar",
                     "cal": cal, "year": year, "month": month,
                     "month_name": month_name, "today": today,
                     "events": events, "hearings": hearings, "tasks": tasks,
                     "prev_month": prev_month, "prev_year": prev_year,
                     "next_month": next_month, "next_year": next_year,
                     "total_hearings": len(hearings), "total_tasks": len(tasks)})
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

