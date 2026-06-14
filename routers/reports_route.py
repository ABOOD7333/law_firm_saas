from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawHearings, LawJudgments,
    LawTransactions, LawExpenses, LawTasks, LawClients, LawParties
)
from dependencies import get_current_user, templates
from core.logger import app_logger

router = APIRouter()


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    from sqlalchemy import func
    try:
        office_id = user.office_id or 1

        # --- Cases stats ---
        total_cases   = db.query(LawCases).filter(LawCases.office_id == office_id).count()
        open_cases    = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.status_key.in_(['ongoing','new','مفتوحة','قيد المتابعة','جديدة','draft'])).count()
        closed_cases  = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.status_key.in_(['closed','مغلقة'])).count()

        # Cases by type
        cases_by_type = db.query(LawCases.case_type_key, func.count(LawCases.id).label('cnt'))\
            .filter(LawCases.office_id == office_id, LawCases.case_type_key != None)\
            .group_by(LawCases.case_type_key).order_by(func.count(LawCases.id).desc()).limit(8).all()

        # Cases by status
        cases_by_status = db.query(LawCases.status_key, func.count(LawCases.id).label('cnt'))\
            .filter(LawCases.office_id == office_id)\
            .group_by(LawCases.status_key).all()

        # --- Financials ---
        income_data = db.query(
            func.substr(LawTransactions.transaction_at, 1, 7).label('month'),
            func.coalesce(func.sum(LawTransactions.amount * LawTransactions.exchange_rate), 0).label('total')
        ).filter(LawTransactions.office_id == office_id)\
         .group_by(func.substr(LawTransactions.transaction_at, 1, 7))\
         .order_by(func.substr(LawTransactions.transaction_at, 1, 7).desc()).limit(6).all()
        income_data = list(reversed(income_data))

        total_income   = db.query(func.coalesce(func.sum(LawTransactions.amount * LawTransactions.exchange_rate), 0))\
            .filter(LawTransactions.office_id == office_id).scalar() or 0
        total_expenses = db.query(func.coalesce(func.sum(LawExpenses.amount * LawExpenses.exchange_rate), 0))\
            .filter(LawExpenses.office_id == office_id).scalar() or 0

        # --- Hearings ---
        total_hearings  = db.query(LawHearings).filter(LawHearings.office_id == office_id).count()
        done_hearings   = db.query(LawHearings).filter(LawHearings.office_id == office_id, LawHearings.status_key == 'completed').count()

        # --- Judgments ---
        total_judgments = db.query(LawJudgments).filter(LawJudgments.office_id == office_id).count()
        won_judgments   = db.query(LawJudgments).filter(LawJudgments.office_id == office_id, LawJudgments.status_key == 'صدر لصالحنا').count()
        lost_judgments  = db.query(LawJudgments).filter(LawJudgments.office_id == office_id, LawJudgments.status_key == 'صدر ضدنا').count()

        # --- Lawyers performance (bulk queries — no N+1) ---
        lawyers = db.query(AccessProfiles).filter(
            AccessProfiles.office_id == office_id,
            AccessProfiles.role.in_(['محامٍ', 'مدير المكتب', 'صاحب المكتب', 'مدير']),
            AccessProfiles.is_active == 1
        ).all()
        lawyer_ids = [l.id for l in lawyers]

        # عدد القضايا لكل محامٍ — استعلام واحد
        cases_agg = dict(
            db.query(LawCases.lead_lawyer_id, func.count(LawCases.id))
            .filter(LawCases.lead_lawyer_id.in_(lawyer_ids))
            .group_by(LawCases.lead_lawyer_id).all()
        ) if lawyer_ids else {}

        # إجمالي المهام لكل محامٍ — استعلام واحد
        tasks_agg = dict(
            db.query(LawTasks.assignee_user_id, func.count(LawTasks.id))
            .filter(LawTasks.assignee_user_id.in_(lawyer_ids),
                    LawTasks.office_id == office_id)
            .group_by(LawTasks.assignee_user_id).all()
        ) if lawyer_ids else {}

        # المهام المكتملة لكل محامٍ — استعلام واحد
        done_agg = dict(
            db.query(LawTasks.assignee_user_id, func.count(LawTasks.id))
            .filter(LawTasks.assignee_user_id.in_(lawyer_ids),
                    LawTasks.office_id == office_id,
                    LawTasks.status_key == 'completed')
            .group_by(LawTasks.assignee_user_id).all()
        ) if lawyer_ids else {}

        lawyer_stats = []
        for lawyer in lawyers:
            tc = tasks_agg.get(lawyer.id, 0)
            dc = done_agg.get(lawyer.id, 0)
            lawyer_stats.append({
                "name":       lawyer.name,
                "role":       lawyer.role,
                "cases":      cases_agg.get(lawyer.id, 0),
                "tasks":      tc,
                "done_tasks": dc,
                "pct":        round(dc / tc * 100) if tc > 0 else 0
            })
        lawyer_stats.sort(key=lambda x: x["cases"], reverse=True)

        # --- Clients ---
        total_clients = db.query(LawClients).filter(LawClients.office_id == office_id).count()
        total_parties = db.query(LawParties).filter(LawParties.office_id == office_id).count()
        total_tasks   = db.query(LawTasks).filter(LawTasks.office_id == office_id).count()
        done_tasks_all = db.query(LawTasks).filter(LawTasks.office_id == office_id, LawTasks.status_key == 'completed').count()

        return templates.TemplateResponse(request=request, name="reports.html", context={
            "user": user, "active_page": "reports",
            "total_cases": total_cases, "open_cases": open_cases, "closed_cases": closed_cases,
            "cases_by_type": cases_by_type, "cases_by_status": cases_by_status,
            "income_data": income_data, "total_income": total_income,
            "total_expenses": total_expenses, "net_profit": total_income - total_expenses,
            "total_hearings": total_hearings, "done_hearings": done_hearings,
            "total_judgments": total_judgments, "won_judgments": won_judgments,
            "lost_judgments": lost_judgments,
            "lawyer_stats": lawyer_stats,
            "total_clients": total_clients, "total_parties": total_parties,
            "total_tasks": total_tasks, "done_tasks_all": done_tasks_all,
        })
    except Exception as exc:
        return safe_error_html(exc, context="reports_route.py")

