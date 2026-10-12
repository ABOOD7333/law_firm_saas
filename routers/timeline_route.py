from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, date
import traceback
from typing import Optional
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawHearings, LawTasks,
    LawJudgments, LawDocuments, LawNotes, LawCorrespondences,
    LawExecutions, LawPowerOfAttorney
)
from dependencies import get_current_user, templates

router = APIRouter()

@router.get("/timeline", response_class=HTMLResponse)
async def timeline_page(
    request: Request,
    case_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not user.office_id:
        raise HTTPException(status_code=403, detail="حسابك غير مرتبط بمكتب")

    try:
        today_str = str(date.today())
        office_id = user.office_id

        # 1. Fetch available cases for office (Fixed multi-tenant isolation!)
        cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        ).order_by(LawCases.title.asc()).all()
        cases_map = {c.id: c for c in cases}

        # 2. Build queries with optional case_id filtering
        hearings_q = db.query(LawHearings).filter(LawHearings.office_id == office_id, LawHearings.is_deleted == 0)
        tasks_q = db.query(LawTasks).filter(LawTasks.office_id == office_id, LawTasks.is_deleted == 0)
        judgments_q = db.query(LawJudgments).filter(LawJudgments.office_id == office_id, LawJudgments.is_deleted == 0)
        documents_q = db.query(LawDocuments).filter(LawDocuments.office_id == office_id, LawDocuments.is_deleted == 0)
        notes_q = db.query(LawNotes).filter(LawNotes.office_id == office_id, LawNotes.is_deleted == 0)
        correspondences_q = db.query(LawCorrespondences).filter(LawCorrespondences.office_id == office_id, LawCorrespondences.is_deleted == 0)
        executions_q = db.query(LawExecutions).filter(LawExecutions.office_id == office_id, LawExecutions.is_deleted == 0)
        poa_q = db.query(LawPowerOfAttorney).filter(LawPowerOfAttorney.office_id == office_id, LawPowerOfAttorney.is_deleted == 0)

        if case_id:
            hearings_q = hearings_q.filter(LawHearings.case_id == case_id)
            tasks_q = tasks_q.filter(LawTasks.case_id == case_id)
            judgments_q = judgments_q.filter(LawJudgments.case_id == case_id)
            documents_q = documents_q.filter(LawDocuments.case_id == case_id)
            notes_q = notes_q.filter(LawNotes.case_id == case_id)
            correspondences_q = correspondences_q.filter(LawCorrespondences.case_id == case_id)
            executions_q = executions_q.filter(LawExecutions.case_id == case_id)
            poa_q = poa_q.filter(LawPowerOfAttorney.case_id == case_id)

        hearings = hearings_q.all()
        tasks = tasks_q.all()
        judgments = judgments_q.all()
        documents = documents_q.all()
        notes = notes_q.all()
        correspondences = correspondences_q.all()
        executions = executions_q.all()
        poas = poa_q.all()

        def _timing(date_str):
            if not date_str: return 'past'
            d = str(date_str)[:10]
            if d == today_str: return 'today'
            if d > today_str: return 'upcoming'
            return 'past'

        def _month_label(date_str):
            if not date_str or len(date_str) < 7: return 'سجل غير محدد'
            year = date_str[:4]
            month = date_str[5:7]
            arabic_months = {
                '01': 'يناير','02': 'فبراير','03': 'مارس','04': 'أبريل',
                '05': 'مايو', '06': 'يونيو', '07': 'يوليو','08': 'أغسطس',
                '09': 'سبتمبر','10': 'أكتوبر','11': 'نوفمبر','12': 'ديسمبر'
            }
            return f"{arabic_months.get(month, month)} {year}"

        events = []

        # Hearings
        for h in hearings:
            d_str = str(h.hearing_at or '')[:10]
            c = cases_map.get(h.case_id)
            events.append({
                'type': 'hearing',
                'type_label': 'جلسة قضائية',
                'icon': 'fa-calendar-days',
                'color': '#3b82f6',
                'title': h.title or 'جلسة مرافعة',
                'date': d_str,
                'case_id': h.case_id,
                'case_title': c.title if c else '',
                'sub': h.result_summary[:80] if getattr(h, 'result_summary', None) else '',
                'status': h.status_key or 'pending',
                'timing': _timing(d_str),
                'month_label': _month_label(d_str[:7] if d_str else '')
            })

        # Tasks
        for t in tasks:
            d_str = str(t.due_at or '')[:10]
            c = cases_map.get(t.case_id) if t.case_id else None
            events.append({
                'type': 'task',
                'type_label': 'مهمة عمل',
                'icon': 'fa-list-check',
                'color': '#f59e0b',
                'title': t.title,
                'date': d_str,
                'case_id': t.case_id,
                'case_title': c.title if c else '',
                'sub': t.description[:80] if t.description else '',
                'status': t.status_key or 'pending',
                'timing': _timing(d_str),
                'month_label': _month_label(d_str[:7] if d_str else '')
            })

        # Judgments
        for j in judgments:
            d_str = str(j.judgment_date or j.created_at or '')[:10]
            c = cases_map.get(j.case_id)
            events.append({
                'type': 'judgment',
                'type_label': 'حكم قضائي',
                'icon': 'fa-gavel',
                'color': '#10b981',
                'title': f"صك حكم #{j.judgment_number}",
                'date': d_str,
                'case_id': j.case_id,
                'case_title': c.title if c else '',
                'sub': (j.operative_clause or '')[:80],
                'status': j.outcome_type or 'صدر الحكم',
                'timing': _timing(d_str),
                'month_label': _month_label(d_str[:7] if d_str else '')
            })

        # Documents
        for d in documents:
            d_str = str(d.created_at or '')[:10]
            c = cases_map.get(d.case_id)
            events.append({
                'type': 'document',
                'type_label': 'وثيقة ومستند',
                'icon': 'fa-folder-open',
                'color': '#8b5cf6',
                'title': getattr(d, 'name', None) or getattr(d, 'doc_code', None) or 'مستند قانوني',
                'date': d_str,
                'case_id': d.case_id,
                'case_title': c.title if c else '',
                'sub': getattr(d, 'document_type_key', '') or getattr(d, 'description', '') or '',
                'status': 'مؤرشف',
                'timing': _timing(d_str),
                'month_label': _month_label(d_str[:7] if d_str else '')
            })

        # Notes & Communications
        for n in notes:
            d_str = str(n.created_at or '')[:10]
            c = cases_map.get(n.case_id)
            events.append({
                'type': 'note',
                'type_label': 'ملاحظة واتصال',
                'icon': 'fa-note-sticky',
                'color': '#ec4899',
                'title': n.title,
                'date': d_str,
                'case_id': n.case_id,
                'case_title': c.title if c else '',
                'sub': n.content[:80] if n.content else '',
                'status': getattr(n, 'communication_channel', '') or 'سجل داخلي',
                'timing': _timing(d_str),
                'month_label': _month_label(d_str[:7] if d_str else '')
            })

        # Correspondences
        for corr in correspondences:
            d_str = str(corr.created_at or '')[:10]
            c = cases_map.get(corr.case_id)
            events.append({
                'type': 'correspondence',
                'type_label': 'مراسلة رسمية',
                'icon': 'fa-envelope',
                'color': '#0ea5e9',
                'title': f"{corr.direction_key}: {corr.subject or corr.letter_number or 'مراسلة رسمية'}",
                'date': d_str,
                'case_id': corr.case_id,
                'case_title': c.title if c else '',
                'sub': getattr(corr, 'registry_number', '') or '',
                'status': corr.direction_key,
                'timing': _timing(d_str),
                'month_label': _month_label(d_str[:7] if d_str else '')
            })

        # Executions
        for ex in executions:
            d_str = str(ex.request_date or ex.created_at or '')[:10]
            c = cases_map.get(ex.case_id)
            events.append({
                'type': 'execution',
                'type_label': 'إجراء تنفيذ',
                'icon': 'fa-scale-unbalanced',
                'color': '#6366f1',
                'title': f"طلب تنفيذ #{ex.execution_number}",
                'date': d_str,
                'case_id': ex.case_id,
                'case_title': c.title if c else '',
                'sub': f"مطالبة: {getattr(ex, 'claimed_amount', 0) or 0} ر.ي | ضد: {getattr(ex, 'debtor_name', '-') or '-'}",
                'status': ex.status_key or 'جاري',
                'timing': _timing(d_str),
                'month_label': _month_label(d_str[:7] if d_str else '')
            })

        # Sort all events chronologically desc
        events.sort(key=lambda x: x['date'] or '', reverse=True)

        # Apply search and type filtering
        if event_type and event_type != 'all':
            events = [e for e in events if e['type'] == event_type]

        if q:
            q_lower = q.lower()
            events = [e for e in events if q_lower in e['title'].lower() or q_lower in e['sub'].lower()]

        # Group by month
        from itertools import groupby
        grouped_events = []
        for month_lbl, group in groupby(events, key=lambda x: x['month_label']):
            grouped_events.append({
                'month': month_lbl,
                'items': list(group)
            })

        kpi_counts = {
            'all': len(events),
            'hearing': len(hearings),
            'task': len(tasks),
            'judgment': len(judgments),
            'document': len(documents),
            'note': len(notes),
            'correspondence': len(correspondences),
            'execution': len(executions)
        }

        return templates.TemplateResponse(
            request=request, name="timeline.html",
            context={
                "user": user,
                "active_page": "timeline",
                "grouped_events": grouped_events,
                "cases": cases,
                "selected_case_id": case_id,
                "event_type": event_type or 'all',
                "q": q or '',
                "hearings": hearings,
                "tasks": tasks,
                "judgments": judgments,
                "documents": documents,
                "notes": notes,
                "correspondences": correspondences,
                "executions": executions,
                "kpis": kpi_counts
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="timeline_route.py")


@router.get("/api/timeline")
async def timeline_api(
    case_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not user.office_id:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    office_id = user.office_id
    hearings_q = db.query(LawHearings).filter(LawHearings.office_id == office_id, LawHearings.is_deleted == 0)
    tasks_q = db.query(LawTasks).filter(LawTasks.office_id == office_id, LawTasks.is_deleted == 0)
    judgments_q = db.query(LawJudgments).filter(LawJudgments.office_id == office_id, LawJudgments.is_deleted == 0)

    if case_id:
        hearings_q = hearings_q.filter(LawHearings.case_id == case_id)
        tasks_q = tasks_q.filter(LawTasks.case_id == case_id)
        judgments_q = judgments_q.filter(LawJudgments.case_id == case_id)

    items = []
    for h in hearings_q.all():
        items.append({"type": "hearing", "title": h.title, "date": str(h.hearing_at or '')[:10], "case_id": h.case_id})
    for t in tasks_q.all():
        items.append({"type": "task", "title": t.title, "date": str(t.due_at or '')[:10], "case_id": t.case_id})
    for j in judgments_q.all():
        items.append({"type": "judgment", "title": f"حكم #{j.judgment_number}", "date": str(j.judgment_date or '')[:10], "case_id": j.case_id})

    items.sort(key=lambda x: x['date'], reverse=True)
    return JSONResponse({"ok": True, "count": len(items), "events": items})
