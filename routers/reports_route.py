from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawHearings, LawJudgments,
    LawTransactions, LawExpenses, LawTasks, LawClients, LawParties, Invoices
)
from dependencies import get_current_user, templates, check_user_permission
from core.logger import app_logger

router = APIRouter()


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    period: str = Query("all", description="تصفية حسب الفترة الزمنية"),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not user.office_id or not check_user_permission(user, "reports", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    try:
        office_id = user.office_id
        now = datetime.now()
        start_date = None

        if period == "month":
            start_date = now.replace(day=1).strftime("%Y-%m-%d")
        elif period == "quarter":
            quarter_month = ((now.month - 1) // 3) * 3 + 1
            start_date = now.replace(month=quarter_month, day=1).strftime("%Y-%m-%d")
        elif period == "year":
            start_date = now.replace(month=1, day=1).strftime("%Y-%m-%d")

        # --- Cases stats (Strictly multi-tenant & soft-delete safe) ---
        cases_base = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
        if start_date:
            cases_base = cases_base.filter(LawCases.created_at >= start_date)

        total_cases = cases_base.count()
        open_cases = cases_base.filter(LawCases.status_key.in_(['ongoing', 'new', 'مفتوحة', 'قيد المتابعة', 'جديدة', 'draft', 'active'])).count()
        closed_cases = cases_base.filter(LawCases.status_key.in_(['closed', 'مغلقة', 'منتهية'])).count()

        # Cases by type
        cases_by_type_q = db.query(LawCases.case_type_key, func.count(LawCases.id).label('cnt'))\
            .filter(LawCases.office_id == office_id, LawCases.is_deleted == 0, LawCases.case_type_key.isnot(None))
        if start_date:
            cases_by_type_q = cases_by_type_q.filter(LawCases.created_at >= start_date)
        cases_by_type_rows = cases_by_type_q.group_by(LawCases.case_type_key).order_by(func.count(LawCases.id).desc()).limit(8).all()
        cases_by_type = [{"case_type_key": r[0] or "عام", "cnt": int(r[1])} for r in cases_by_type_rows]

        # Cases by status
        cases_by_status_q = db.query(LawCases.status_key, func.count(LawCases.id).label('cnt'))\
            .filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
        if start_date:
            cases_by_status_q = cases_by_status_q.filter(LawCases.created_at >= start_date)
        cases_by_status_rows = cases_by_status_q.group_by(LawCases.status_key).all()
        cases_by_status = [{"status_key": r[0] or "غير محدد", "cnt": int(r[1])} for r in cases_by_status_rows]

        # --- Financials (Strictly multi-tenant & soft-delete safe) ---
        trans_q = db.query(LawTransactions).filter(
            LawTransactions.office_id == office_id,
            LawTransactions.is_deleted == 0
        )
        exp_q = db.query(LawExpenses).filter(
            LawExpenses.office_id == office_id,
            LawExpenses.is_deleted == 0
        )
        if start_date:
            trans_q = trans_q.filter(LawTransactions.transaction_at >= start_date)
            exp_q = exp_q.filter(LawExpenses.expense_at >= start_date)

        income_rows = db.query(
            func.substr(LawTransactions.transaction_at, 1, 7).label('month'),
            func.coalesce(func.sum(LawTransactions.amount * func.coalesce(LawTransactions.exchange_rate, 1.0)), 0).label('total')
        ).filter(
            LawTransactions.office_id == office_id,
            LawTransactions.is_deleted == 0
        ).group_by(func.substr(LawTransactions.transaction_at, 1, 7))\
         .order_by(func.substr(LawTransactions.transaction_at, 1, 7).desc()).limit(6).all()
        income_data = [{"month": r[0], "total": float(r[1])} for r in reversed(income_rows)]

        total_income = db.query(func.coalesce(func.sum(LawTransactions.amount * func.coalesce(LawTransactions.exchange_rate, 1.0)), 0))\
            .filter(LawTransactions.office_id == office_id, LawTransactions.is_deleted == 0)
        if start_date:
            total_income = total_income.filter(LawTransactions.transaction_at >= start_date)
        total_income = total_income.scalar() or 0.0

        total_expenses = db.query(func.coalesce(func.sum(LawExpenses.amount * func.coalesce(LawExpenses.exchange_rate, 1.0)), 0))\
            .filter(LawExpenses.office_id == office_id, LawExpenses.is_deleted == 0)
        if start_date:
            total_expenses = total_expenses.filter(LawExpenses.expense_at >= start_date)
        total_expenses = total_expenses.scalar() or 0.0

        net_profit = total_income - total_expenses
        profit_margin = round((net_profit / total_income * 100), 1) if total_income > 0 else 0.0

        # --- Invoices (ZATCA & e-Invoicing Stats) ---
        inv_q = db.query(Invoices).filter(Invoices.office_id == office_id, Invoices.is_deleted == 0)
        if start_date:
            inv_q = inv_q.filter(Invoices.issue_date >= start_date)
        total_invoices_count = inv_q.count()
        paid_invoices_count = inv_q.filter(Invoices.status == 'Paid').count()
        collection_rate = round((paid_invoices_count / total_invoices_count * 100), 1) if total_invoices_count > 0 else 0.0

        # --- Hearings (Strictly multi-tenant & soft-delete safe) ---
        hearings_q = db.query(LawHearings).filter(LawHearings.office_id == office_id, LawHearings.is_deleted == 0)
        if start_date:
            hearings_q = hearings_q.filter(LawHearings.hearing_at >= start_date)
        total_hearings = hearings_q.count()
        done_hearings = hearings_q.filter(LawHearings.status_key == 'completed').count()

        # --- Judgments (Strictly multi-tenant & soft-delete safe) ---
        judgments_q = db.query(LawJudgments).filter(LawJudgments.office_id == office_id, LawJudgments.is_deleted == 0)
        if start_date:
            judgments_q = judgments_q.filter(LawJudgments.judgment_date >= start_date)
        total_judgments = judgments_q.count()
        won_judgments = judgments_q.filter(LawJudgments.status_key.in_(['صدر لصالحنا', 'favorable', 'won'])).count()
        lost_judgments = judgments_q.filter(LawJudgments.status_key.in_(['صدر ضدنا', 'unfavorable', 'lost'])).count()
        win_rate = round((won_judgments / total_judgments * 100), 1) if total_judgments > 0 else 0.0

        # --- Lawyers performance (bulk queries — zero N+1) ---
        lawyers = db.query(AccessProfiles).filter(
            AccessProfiles.office_id == office_id,
            AccessProfiles.is_deleted == 0,
            AccessProfiles.role.in_(['محامٍ', 'محامي', 'مدير المكتب', 'صاحب المكتب', 'مدير']),
            AccessProfiles.is_active == 1
        ).all()
        lawyer_ids = [l.id for l in lawyers]

        cases_agg = dict(
            db.query(LawCases.lead_lawyer_id, func.count(LawCases.id))
            .filter(LawCases.office_id == office_id, LawCases.is_deleted == 0, LawCases.lead_lawyer_id.in_(lawyer_ids))
            .group_by(LawCases.lead_lawyer_id).all()
        ) if lawyer_ids else {}

        tasks_agg = dict(
            db.query(LawTasks.assignee_user_id, func.count(LawTasks.id))
            .filter(LawTasks.assignee_user_id.in_(lawyer_ids),
                    LawTasks.office_id == office_id,
                    LawTasks.is_deleted == 0)
            .group_by(LawTasks.assignee_user_id).all()
        ) if lawyer_ids else {}

        done_agg = dict(
            db.query(LawTasks.assignee_user_id, func.count(LawTasks.id))
            .filter(LawTasks.assignee_user_id.in_(lawyer_ids),
                    LawTasks.office_id == office_id,
                    LawTasks.is_deleted == 0,
                    LawTasks.status_key == 'completed')
            .group_by(LawTasks.assignee_user_id).all()
        ) if lawyer_ids else {}

        lawyer_stats = []
        for lawyer in lawyers:
            tc = tasks_agg.get(lawyer.id, 0)
            dc = done_agg.get(lawyer.id, 0)
            lawyer_stats.append({
                "name": lawyer.name,
                "role": lawyer.role,
                "cases": cases_agg.get(lawyer.id, 0),
                "tasks": tc,
                "done_tasks": dc,
                "pct": round(dc / tc * 100) if tc > 0 else 0
            })
        lawyer_stats.sort(key=lambda x: (x["cases"], x["done_tasks"]), reverse=True)

        # --- Clients & Tasks (Strictly multi-tenant & soft-delete safe) ---
        total_clients = db.query(LawClients).filter(LawClients.office_id == office_id, LawClients.is_deleted == 0).count()
        total_parties = db.query(LawParties).filter(LawParties.office_id == office_id, LawParties.is_deleted == 0).count()
        
        tasks_base = db.query(LawTasks).filter(LawTasks.office_id == office_id, LawTasks.is_deleted == 0)
        if start_date:
            tasks_base = tasks_base.filter(LawTasks.created_at >= start_date)
        total_tasks = tasks_base.count()
        done_tasks_all = tasks_base.filter(LawTasks.status_key == 'completed').count()
        task_completion_rate = round((done_tasks_all / total_tasks * 100), 1) if total_tasks > 0 else 0.0

        return templates.TemplateResponse(request=request, name="reports.html", context={
            "user": user,
            "active_page": "reports",
            "period": period,
            "total_cases": total_cases,
            "open_cases": open_cases,
            "closed_cases": closed_cases,
            "cases_by_type": cases_by_type,
            "cases_by_status": cases_by_status,
            "income_data": income_data,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "profit_margin": profit_margin,
            "total_invoices_count": total_invoices_count,
            "paid_invoices_count": paid_invoices_count,
            "collection_rate": collection_rate,
            "total_hearings": total_hearings,
            "done_hearings": done_hearings,
            "total_judgments": total_judgments,
            "won_judgments": won_judgments,
            "lost_judgments": lost_judgments,
            "win_rate": win_rate,
            "lawyer_stats": lawyer_stats,
            "total_clients": total_clients,
            "total_parties": total_parties,
            "total_tasks": total_tasks,
            "done_tasks_all": done_tasks_all,
            "task_completion_rate": task_completion_rate,
        })
    except Exception as exc:
        return safe_error_html(exc, context="reports_route.py")


@router.get("/api/reports/summary")
async def reports_summary_api(
    period: str = Query("all"),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not user.office_id or not check_user_permission(user, "reports", "view"):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    office_id = user.office_id
    total_cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).count()
    total_income = db.query(func.coalesce(func.sum(LawTransactions.amount * func.coalesce(LawTransactions.exchange_rate, 1.0)), 0))\
        .filter(LawTransactions.office_id == office_id, LawTransactions.is_deleted == 0).scalar() or 0.0
    total_expenses = db.query(func.coalesce(func.sum(LawExpenses.amount * func.coalesce(LawExpenses.exchange_rate, 1.0)), 0))\
        .filter(LawExpenses.office_id == office_id, LawExpenses.is_deleted == 0).scalar() or 0.0

    return JSONResponse({
        "success": True,
        "office_id": office_id,
        "period": period,
        "cases_count": total_cases,
        "total_income": float(total_income),
        "total_expenses": float(total_expenses),
        "net_profit": float(total_income - total_expenses)
    })
