from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import traceback

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawHearings, LawTasks,
    LawJudgments, LawDocuments, LawNotes, LawCorrespondences
)
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/timeline", response_class=HTMLResponse)
async def timeline_page(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        from datetime import date as _date
        today_str = str(_date.today())

        # Determine office scope
        office_id = user.office_id or 1

        # --- Fetch all data ---
        hearings      = db.query(LawHearings).filter(LawHearings.office_id == office_id).all()
        tasks         = db.query(LawTasks).filter(LawTasks.office_id == office_id).all()
        judgments     = db.query(LawJudgments).filter(LawJudgments.office_id == office_id).all()
        documents     = db.query(LawDocuments).filter(LawDocuments.office_id == office_id).all()
        notes         = db.query(LawNotes).filter(LawNotes.office_id == office_id).all()
        correspondences = db.query(LawCorrespondences).filter(LawCorrespondences.office_id == office_id).all()
        cases         = db.query(LawCases).filter(LawCases.is_deleted == 0).all()

        # Build cases lookup
        cases_map = {c.id: c for c in cases}

        def _timing(date_str):
            if not date_str: return 'past'
            d = str(date_str)[:10]
            if d == today_str: return 'today'
            if d > today_str:  return 'upcoming'
            return 'past'

        def _month_label(date_str):
            """Convert YYYY-MM to Arabic month label"""
            if not date_str or len(date_str) < 7: return ''
            year  = date_str[:4]
            month = date_str[5:7]
            arabic_months = {
                '01': 'يناير','02': 'فبراير','03': 'مارس','04': 'أبريل',
                '05': 'مايو', '06': 'يونيو', '07': 'يوليو','08': 'أغسطس',
                '09': 'سبتمبر','10': 'أكتوبر','11': 'نوفمبر','12': 'ديسمبر'
            }
            return f"{arabic_months.get(month, month)} {year}"

        def _status_chip(status_key, event_type):
            mapping = {
                'hearing': {
                    'pending':     {'cls': 'chip-pending',     'label': 'قيد الانتظار'},
                    'completed':   {'cls': 'chip-completed',   'label': 'منتهية'},
                    'in_progress': {'cls': 'chip-in_progress', 'label': 'جارية'},
                },
                'task': {
                    'pending':     {'cls': 'chip-pending',     'label': 'قيد الانتظار'},
                    'in_progress': {'cls': 'chip-in_progress', 'label': 'قيد التنفيذ'},
                    'completed':   {'cls': 'chip-completed',   'label': 'مكتملة'},
                },
                'judgment': {
                    'صدر لصالحنا': {'cls': 'chip-win',  'label': 'لصالحنا'},
                    'صدر ضدنا':    {'cls': 'chip-lose', 'label': 'ضدنا'},
                },
            }
            chip = mapping.get(event_type, {}).get(status_key)
            if not chip and status_key:
                chip = {'cls': 'chip-default', 'label': status_key}
            return chip

        events = []

        # Hearings
        for h in hearings:
            date_str = str(h.hearing_at or '')[:10]
            case = cases_map.get(h.case_id)
            events.append({
                'type':       'hearing',
                'type_label': 'جلسة قضائية',
                'icon':       'fa-calendar-days',
                'title':      h.title,
                'date':       date_str,
                'case_id':    h.case_id,
                'case_title': case.title if case else '',
                'sub':        h.result_summary[:60] if h.result_summary else '',
                'status_chip': _status_chip(h.status_key, 'hearing'),
                'timing':     _timing(date_str),
                'month_label': _month_label(date_str[:7] if date_str else ''),
            })

        # Tasks
        for t in tasks:
            date_str = str(t.due_at or '')[:10]
            case = cases_map.get(t.case_id) if t.case_id else None
            events.append({
                'type':       'task',
                'type_label': 'مهمة',
                'icon':       'fa-list-check',
                'title':      t.title,
                'date':       date_str,
                'case_id':    t.case_id,
                'case_title': case.title if case else '',
                'sub':        t.description[:60] if t.description else '',
                'status_chip': _status_chip(t.status_key, 'task'),
                'timing':     _timing(date_str),
                'month_label': _month_label(date_str[:7] if date_str else ''),
            })

        # Judgments
        for j in judgments:
            date_str = str(j.judgment_date or '')[:10]
            case = cases_map.get(j.case_id)
            events.append({
                'type':       'judgment',
                'type_label': 'حكم قضائي',
                'icon':       'fa-scale-balanced',
                'title':      f"حكم – {j.court_name or 'محكمة غير محددة'}",
                'date':       date_str,
                'case_id':    j.case_id,
                'case_title': case.title if case else '',
                'sub':        j.judge_name or '',
                'status_chip': _status_chip(j.status_key, 'judgment'),
                'timing':     _timing(date_str),
                'month_label': _month_label(date_str[:7] if date_str else ''),
            })

        # Documents
        for d in documents:
            date_str = str(d.doc_date or d.created_at or '')[:10]
            case = cases_map.get(d.case_id)
            events.append({
                'type':       'doc',
                'type_label': 'وثيقة',
                'icon':       'fa-file-lines',
                'title':      d.name,
                'date':       date_str,
                'case_id':    d.case_id,
                'case_title': case.title if case else '',
                'sub':        d.document_type_key or '',
                'status_chip': None,
                'timing':     _timing(date_str),
                'month_label': _month_label(date_str[:7] if date_str else ''),
            })

        # Notes
        for n in notes:
            date_str = str(n.created_at or '')[:10]
            case = cases_map.get(n.case_id)
            events.append({
                'type':       'note',
                'type_label': 'ملاحظة',
                'icon':       'fa-note-sticky',
                'title':      n.title,
                'date':       date_str,
                'case_id':    n.case_id,
                'case_title': case.title if case else '',
                'sub':        (n.content or '')[:60],
                'status_chip': None,
                'timing':     _timing(date_str),
                'month_label': _month_label(date_str[:7] if date_str else ''),
            })

        # Correspondences
        for c in correspondences:
            date_str = str(c.letter_date or c.created_at or '')[:10]
            case = cases_map.get(c.case_id)
            events.append({
                'type':       'corr',
                'type_label': 'مراسلة رسمية',
                'icon':       'fa-envelope',
                'title':      c.subject or f"مراسلة رقم {c.letter_number or c.id}",
                'date':       date_str,
                'case_id':    c.case_id,
                'case_title': case.title if case else '',
                'sub':        c.direction_key or '',
                'status_chip': None,
                'timing':     _timing(date_str),
                'month_label': _month_label(date_str[:7] if date_str else ''),
            })

        # Sort descending (most recent first), empty dates go to bottom
        events.sort(key=lambda x: x['date'] or '0000-00-00', reverse=True)

        return templates.TemplateResponse(request=request, name="timeline.html", context={
            "user": user,
            "active_page": "timeline",
            "events": events,
            "cases": cases,
            "hearings": hearings,
            "tasks": tasks,
            "judgments": judgments,
            "documents": documents,
            "notes": notes,
            "correspondences": correspondences,
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)



