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

        # --- 1. Cases stats (Multi-tenant & soft-delete safe) ---
        total_cases = 0
        open_cases = 0
        closed_cases = 0
        cases_by_type = []
        cases_by_status = []
        try:
            cases_base = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
            if start_date:
                cases_base = cases_base.filter(LawCases.created_at >= start_date)

            total_cases = cases_base.count()
            open_cases = cases_base.filter(LawCases.status_key.in_(['ongoing', 'new', 'مفتوحة', 'قيد المتابعة', 'جديدة', 'draft', 'active'])).count()
            closed_cases = cases_base.filter(LawCases.status_key.in_(['closed', 'مغلقة', 'منتهية'])).count()

            # Cases by type
            cases_type_rows = db.query(LawCases.case_type_key)\
                .filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
            if start_date:
                cases_type_rows = cases_type_rows.filter(LawCases.created_at >= start_date)
            type_counter = {}
            for (ct,) in cases_type_rows.all():
                k = ct or "عام"
                type_counter[k] = type_counter.get(k, 0) + 1
            sorted_types = sorted(type_counter.items(), key=lambda x: x[1], reverse=True)[:8]
            cases_by_type = [{"case_type_key": k, "cnt": v} for k, v in sorted_types]

            # Cases by status
            cases_status_rows = db.query(LawCases.status_key)\
                .filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
            if start_date:
                cases_status_rows = cases_status_rows.filter(LawCases.created_at >= start_date)
            status_counter = {}
            for (st,) in cases_status_rows.all():
                k = st or "غير محدد"
                status_counter[k] = status_counter.get(k, 0) + 1
            cases_by_status = [{"status_key": k, "cnt": v} for k, v in status_counter.items()]
        except Exception as e_cases:
            db.rollback()
            app_logger.warning(f"[Reports] Cases stats query error: {e_cases}")

        # --- 2. Financials (Safe cross-database aggregation for PostgreSQL & SQLite) ---
        income_data = []
        total_income = 0.0
        total_expenses = 0.0
        try:
            trans_rows = db.query(
                LawTransactions.transaction_at,
                LawTransactions.amount,
                getattr(LawTransactions, 'exchange_rate', None)
            ).filter(
                LawTransactions.office_id == office_id,
                LawTransactions.is_deleted == 0
            ).all()

            monthly_totals = {}
            for t in trans_rows:
                d_str = str(t[0] or '')
                rate = float(t[2]) if (len(t) > 2 and t[2] is not None) else 1.0
                amt = (float(t[1]) if t[1] is not None else 0.0) * rate
                if not start_date or d_str >= start_date:
                    total_income += amt
                m_key = d_str[:7]
                if len(m_key) == 7:
                    monthly_totals[m_key] = monthly_totals.get(m_key, 0.0) + amt

            sorted_months = sorted(monthly_totals.keys())[-6:]
            income_data = [{"month": m, "total": round(monthly_totals[m], 2)} for m in sorted_months]
        except Exception as e_trans:
            db.rollback()
            app_logger.warning(f"[Reports] Transactions query error: {e_trans}")

        try:
            exp_rows = db.query(
                LawExpenses.expense_at,
                LawExpenses.amount,
                getattr(LawExpenses, 'exchange_rate', None)
            ).filter(
                LawExpenses.office_id == office_id,
                LawExpenses.is_deleted == 0
            ).all()

            for e in exp_rows:
                d_str = str(e[0] or '')
                rate = float(e[2]) if (len(e) > 2 and e[2] is not None) else 1.0
                amt = (float(e[1]) if e[1] is not None else 0.0) * rate
                if not start_date or d_str >= start_date:
                    total_expenses += amt
        except Exception as e_exp:
            db.rollback()
            app_logger.warning(f"[Reports] Expenses query error: {e_exp}")

        net_profit = total_income - total_expenses
        profit_margin = round((net_profit / total_income * 100), 1) if total_income > 0 else 0.0

        # --- 3. Invoices (e-Invoicing Stats) ---
        total_invoices_count = 0
        paid_invoices_count = 0
        collection_rate = 0.0
        try:
            inv_q = db.query(Invoices).filter(Invoices.office_id == office_id, Invoices.is_deleted == 0)
            if start_date:
                inv_q = inv_q.filter(Invoices.issue_date >= start_date)
            total_invoices_count = inv_q.count()
            paid_invoices_count = inv_q.filter(Invoices.status == 'Paid').count()
            collection_rate = round((paid_invoices_count / total_invoices_count * 100), 1) if total_invoices_count > 0 else 0.0
        except Exception as e_inv:
            db.rollback()
            app_logger.warning(f"[Reports] Invoices query error: {e_inv}")

        # --- 4. Hearings (Multi-tenant & soft-delete safe) ---
        total_hearings = 0
        done_hearings = 0
        try:
            hearings_q = db.query(LawHearings).filter(LawHearings.office_id == office_id, LawHearings.is_deleted == 0)
            if start_date:
                hearings_q = hearings_q.filter(LawHearings.hearing_at >= start_date)
            total_hearings = hearings_q.count()
            done_hearings = hearings_q.filter(LawHearings.status_key == 'completed').count()
        except Exception as e_hear:
            db.rollback()
            app_logger.warning(f"[Reports] Hearings query error: {e_hear}")

        # --- 5. Judgments (Multi-tenant & soft-delete safe) ---
        total_judgments = 0
        won_judgments = 0
        lost_judgments = 0
        win_rate = 0.0
        try:
            judgments_q = db.query(LawJudgments).filter(LawJudgments.office_id == office_id, LawJudgments.is_deleted == 0)
            if start_date:
                judgments_q = judgments_q.filter(LawJudgments.judgment_date >= start_date)
            total_judgments = judgments_q.count()
            won_judgments = judgments_q.filter(LawJudgments.status_key.in_(['صدر لصالحنا', 'favorable', 'won'])).count()
            lost_judgments = judgments_q.filter(LawJudgments.status_key.in_(['صدر ضدنا', 'unfavorable', 'lost'])).count()
            win_rate = round((won_judgments / total_judgments * 100), 1) if total_judgments > 0 else 0.0
        except Exception as e_judg:
            db.rollback()
            app_logger.warning(f"[Reports] Judgments query error: {e_judg}")

        # --- 6. Lawyers performance (Safe bulk queries) ---
        lawyer_stats = []
        try:
            lawyers = db.query(AccessProfiles).filter(
                AccessProfiles.office_id == office_id,
                AccessProfiles.is_deleted == 0,
                AccessProfiles.role.in_(['محامٍ', 'محامي', 'مدير المكتب', 'صاحب المكتب', 'مدير', 'مدير النظام', 'مستشار', 'admin', 'owner']),
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
        except Exception as e_lawyers:
            db.rollback()
            app_logger.warning(f"[Reports] Lawyers performance query error: {e_lawyers}")

        # --- 7. Clients, Parties & Tasks ---
        total_clients = 0
        total_parties = 0
        total_tasks = 0
        done_tasks_all = 0
        task_completion_rate = 0.0
        try:
            total_clients = db.query(LawClients).filter(LawClients.office_id == office_id, LawClients.is_deleted == 0).count()
            total_parties = db.query(LawParties).filter(LawParties.office_id == office_id, LawParties.is_deleted == 0).count()
            
            tasks_base = db.query(LawTasks).filter(LawTasks.office_id == office_id, LawTasks.is_deleted == 0)
            if start_date:
                tasks_base = tasks_base.filter(LawTasks.created_at >= start_date)
            total_tasks = tasks_base.count()
            done_tasks_all = tasks_base.filter(LawTasks.status_key == 'completed').count()
            task_completion_rate = round((done_tasks_all / total_tasks * 100), 1) if total_tasks > 0 else 0.0
        except Exception as e_tasks:
            db.rollback()
            app_logger.warning(f"[Reports] Tasks/Clients query error: {e_tasks}")

        context_data = {
            "request": request,
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
        }

        return templates.TemplateResponse("reports.html", context_data)
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
    total_cases = 0
    total_income = 0.0
    total_expenses = 0.0
    try:
        total_cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).count()
        total_income = db.query(func.coalesce(func.sum(LawTransactions.amount * func.coalesce(LawTransactions.exchange_rate, 1.0)), 0))\
            .filter(LawTransactions.office_id == office_id, LawTransactions.is_deleted == 0).scalar() or 0.0
        total_expenses = db.query(func.coalesce(func.sum(LawExpenses.amount * func.coalesce(LawExpenses.exchange_rate, 1.0)), 0))\
            .filter(LawExpenses.office_id == office_id, LawExpenses.is_deleted == 0).scalar() or 0.0
    except Exception as e:
        db.rollback()
        app_logger.warning(f"[Reports API] Summary error: {e}")

    return JSONResponse({
        "success": True,
        "office_id": office_id,
        "period": period,
        "cases_count": total_cases,
        "total_income": float(total_income),
        "total_expenses": float(total_expenses),
        "net_profit": float(total_income - total_expenses)
    })
