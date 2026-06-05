"""
محرك استعلام قاعدة البيانات
يسحب البيانات الحقيقية للمكتب ويجيب على الأسئلة
DB Query Engine - Pulls real office data and answers queries
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import json

from database.models import (
    LawCases,
    LawClients,
    LawHearings,
    LawTasks,
    LawTransactions,
    LawExpenses,
    LawParties,
    LawJudgments,
    LawDocuments,
    LawPleadings,
    LawExecutions,
    LawCorrespondences,
    LawNotes,
    LawLimitations,
    LawPowerOfAttorney,
    LawTimesheets,
    LawRequest,
    AccessProfiles,
    LawTemplates,
)


def _today_str() -> str:
    return date.today().isoformat()


def _now_str() -> str:
    return datetime.now().isoformat()


class DBQueryEngine:
    """
    محرك الاستعلام يعرف كيف يتعامل مع نماذج SQLAlchemy الحقيقية
    لمكتب المحاماة ويُجيب على أي سؤال متعلق بالبيانات.
    """

    def __init__(self, db: Session, office_id: int, user_id: int):
        self.db = db
        self.office_id = office_id
        self.user_id = user_id

    # ══════════════════════════════════════════
    # 1. إحصائيات القضايا
    # ══════════════════════════════════════════

    def get_cases_stats(self) -> Dict:
        """إحصائيات شاملة لقضايا المكتب"""
        base = self.db.query(LawCases).filter(
            LawCases.office_id == self.office_id,
            LawCases.is_deleted == 0,
        )

        total = base.count()
        open_cases = base.filter(
            LawCases.status_key.in_(["open", "active", "draft", "in_progress"])
        ).count()
        closed_cases = base.filter(
            LawCases.status_key.in_(["closed", "completed", "done"])
        ).count()

        # هذا الشهر
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        this_month = base.filter(
            LawCases.created_at >= month_start
        ).count()

        # هذا العام
        year_start = today.replace(month=1, day=1).isoformat()
        this_year = base.filter(
            LawCases.created_at >= year_start
        ).count()

        # تصنيف حسب النوع
        by_type_rows = (
            self.db.query(LawCases.case_type_key, func.count(LawCases.id))
            .filter(LawCases.office_id == self.office_id, LawCases.is_deleted == 0)
            .group_by(LawCases.case_type_key)
            .all()
        )
        by_type = {row[0] or "غير محدد": row[1] for row in by_type_rows}

        # القضايا المضافة اليوم
        today_str = _today_str()
        added_today = base.filter(
            func.date(LawCases.created_at) == today_str
        ).count()

        return {
            "total": total,
            "open": open_cases,
            "closed": closed_cases,
            "this_month": this_month,
            "this_year": this_year,
            "added_today": added_today,
            "by_type": by_type,
        }

    def get_case_by_number(self, case_number: str) -> Optional[Dict]:
        """الحصول على تفاصيل قضية بواسطة رقمها"""
        case = (
            self.db.query(LawCases)
            .filter(
                LawCases.office_id == self.office_id,
                LawCases.case_number == case_number.strip(),
                LawCases.is_deleted == 0,
            )
            .first()
        )
        if not case:
            return None

        return {
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
            "summary": case.summary,
            "status": case.status_key,
            "case_type": case.case_type_key,
            "open_date": case.open_date,
            "close_date": case.close_date,
            "estimated_fee": case.estimated_fee,
            "claim_amount": case.claim_amount,
            "created_at": case.created_at,
        }

    def get_recent_cases(self, limit: int = 10) -> List[Dict]:
        """آخر القضايا المضافة"""
        cases = (
            self.db.query(LawCases)
            .filter(
                LawCases.office_id == self.office_id,
                LawCases.is_deleted == 0,
            )
            .order_by(LawCases.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "case_number": c.case_number,
                "title": c.title,
                "status": c.status_key,
                "case_type": c.case_type_key,
                "created_at": c.created_at,
            }
            for c in cases
        ]

    # ══════════════════════════════════════════
    # 2. الجلسات
    # ══════════════════════════════════════════

    def get_today_hearings(self) -> List[Dict]:
        """جلسات اليوم"""
        today_str = _today_str()
        hearings = (
            self.db.query(LawHearings)
            .join(LawCases, LawHearings.case_id == LawCases.id)
            .filter(
                LawHearings.office_id == self.office_id,
                LawHearings.is_deleted == 0,
                func.date(LawHearings.hearing_at) == today_str,
            )
            .order_by(LawHearings.hearing_at)
            .all()
        )
        return [self._format_hearing(h) for h in hearings]

    def get_tomorrow_hearings(self) -> List[Dict]:
        """جلسات الغد"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        hearings = (
            self.db.query(LawHearings)
            .filter(
                LawHearings.office_id == self.office_id,
                LawHearings.is_deleted == 0,
                func.date(LawHearings.hearing_at) == tomorrow,
            )
            .order_by(LawHearings.hearing_at)
            .all()
        )
        return [self._format_hearing(h) for h in hearings]

    def get_upcoming_hearings(self, days: int = 7) -> List[Dict]:
        """الجلسات القادمة خلال عدد أيام محدد"""
        today = date.today()
        end_date = (today + timedelta(days=days)).isoformat()
        today_str = today.isoformat()

        hearings = (
            self.db.query(LawHearings)
            .filter(
                LawHearings.office_id == self.office_id,
                LawHearings.is_deleted == 0,
                func.date(LawHearings.hearing_at) >= today_str,
                func.date(LawHearings.hearing_at) <= end_date,
            )
            .order_by(LawHearings.hearing_at)
            .all()
        )
        return [self._format_hearing(h) for h in hearings]

    def get_hearings_this_week(self) -> List[Dict]:
        """جلسات هذا الأسبوع"""
        return self.get_upcoming_hearings(days=7)

    def get_hearings_this_month(self) -> List[Dict]:
        """جلسات هذا الشهر"""
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        # آخر يوم في الشهر
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        month_end = (next_month - timedelta(days=1)).isoformat()

        hearings = (
            self.db.query(LawHearings)
            .filter(
                LawHearings.office_id == self.office_id,
                LawHearings.is_deleted == 0,
                func.date(LawHearings.hearing_at) >= month_start,
                func.date(LawHearings.hearing_at) <= month_end,
            )
            .order_by(LawHearings.hearing_at)
            .all()
        )
        return [self._format_hearing(h) for h in hearings]

    def _format_hearing(self, h: LawHearings) -> Dict:
        """تنسيق بيانات الجلسة"""
        # جلب عنوان القضية
        case_title = ""
        case_number = ""
        if h.case_id:
            c = self.db.query(LawCases.title, LawCases.case_number).filter(
                LawCases.id == h.case_id
            ).first()
            if c:
                case_title = c.title
                case_number = c.case_number

        return {
            "id": h.id,
            "title": h.title,
            "hearing_at": h.hearing_at,
            "status": h.status_key,
            "result_summary": h.result_summary,
            "next_hearing_date": h.next_hearing_date,
            "case_id": h.case_id,
            "case_title": case_title,
            "case_number": case_number,
        }

    # ══════════════════════════════════════════
    # 3. الموكلون
    # ══════════════════════════════════════════

    def get_clients_stats(self) -> Dict:
        """إحصائيات الموكلين"""
        base = self.db.query(LawClients).filter(
            LawClients.office_id == self.office_id,
            LawClients.is_deleted == 0,
        )

        total = base.count()

        today_str = date.today().replace(day=1).isoformat()
        this_month = base.filter(
            LawClients.created_at >= today_str
        ).count()

        return {
            "total": total,
            "this_month": this_month,
        }

    def search_clients(self, keyword: str) -> List[Dict]:
        """البحث في الموكلين"""
        kw = f"%{keyword.strip()}%"
        clients = (
            self.db.query(LawClients)
            .filter(
                LawClients.office_id == self.office_id,
                LawClients.is_deleted == 0,
                or_(
                    LawClients.name.ilike(kw),
                    LawClients.phone.ilike(kw),
                    LawClients.national_id.ilike(kw),
                ),
            )
            .limit(20)
            .all()
        )
        return [
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "email": c.email,
                "case_number": c.case_number,
                "national_id": c.national_id,
                "created_at": c.created_at,
            }
            for c in clients
        ]

    # ══════════════════════════════════════════
    # 4. المالية
    # ══════════════════════════════════════════

    def get_finance_summary(self) -> Dict:
        """ملخص مالي شامل"""
        # الإيرادات (المعاملات المالية المكتملة)
        income_row = (
            self.db.query(func.sum(LawTransactions.amount))
            .join(LawCases, LawTransactions.case_id == LawCases.id)
            .filter(
                LawTransactions.office_id == self.office_id,
                LawTransactions.is_deleted == 0,
                LawTransactions.status_key == "paid",
            )
            .scalar()
        )
        total_income = float(income_row or 0)

        # الإيرادات المعلقة
        pending_income_row = (
            self.db.query(func.sum(LawTransactions.amount))
            .filter(
                LawTransactions.office_id == self.office_id,
                LawTransactions.is_deleted == 0,
                LawTransactions.status_key == "pending",
            )
            .scalar()
        )
        pending_income = float(pending_income_row or 0)

        # المصروفات
        expense_row = (
            self.db.query(func.sum(LawExpenses.amount))
            .filter(
                LawExpenses.office_id == self.office_id,
                LawExpenses.is_deleted == 0,
            )
            .scalar()
        )
        total_expenses = float(expense_row or 0)

        # هذا الشهر
        month_start = date.today().replace(day=1).isoformat()
        income_month = (
            self.db.query(func.sum(LawTransactions.amount))
            .filter(
                LawTransactions.office_id == self.office_id,
                LawTransactions.is_deleted == 0,
                LawTransactions.status_key == "paid",
                LawTransactions.transaction_at >= month_start,
            )
            .scalar()
        )
        this_month_income = float(income_month or 0)

        # هذا العام
        year_start = date.today().replace(month=1, day=1).isoformat()
        income_year = (
            self.db.query(func.sum(LawTransactions.amount))
            .filter(
                LawTransactions.office_id == self.office_id,
                LawTransactions.is_deleted == 0,
                LawTransactions.status_key == "paid",
                LawTransactions.transaction_at >= year_start,
            )
            .scalar()
        )
        this_year_income = float(income_year or 0)

        net_profit = total_income - total_expenses

        return {
            "total_income": total_income,
            "pending_income": pending_income,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "this_month_income": this_month_income,
            "this_year_income": this_year_income,
        }

    def get_finance_by_period(self, start_date: str, end_date: str) -> Dict:
        """الملخص المالي لفترة محددة"""
        income = (
            self.db.query(func.sum(LawTransactions.amount))
            .filter(
                LawTransactions.office_id == self.office_id,
                LawTransactions.is_deleted == 0,
                LawTransactions.transaction_at >= start_date,
                LawTransactions.transaction_at <= end_date,
            )
            .scalar()
        )
        expenses = (
            self.db.query(func.sum(LawExpenses.amount))
            .filter(
                LawExpenses.office_id == self.office_id,
                LawExpenses.is_deleted == 0,
                LawExpenses.expense_at >= start_date,
                LawExpenses.expense_at <= end_date,
            )
            .scalar()
        )
        income_val = float(income or 0)
        expenses_val = float(expenses or 0)

        return {
            "period_start": start_date,
            "period_end": end_date,
            "income": income_val,
            "expenses": expenses_val,
            "net": income_val - expenses_val,
        }

    # ══════════════════════════════════════════
    # 5. المهام
    # ══════════════════════════════════════════

    def get_pending_tasks(self) -> List[Dict]:
        """جميع المهام المعلقة"""
        tasks = (
            self.db.query(LawTasks)
            .filter(
                LawTasks.office_id == self.office_id,
                LawTasks.is_deleted == 0,
                LawTasks.status_key.in_(["pending", "in_progress", "open"]),
            )
            .order_by(LawTasks.due_at.asc().nullslast(), LawTasks.priority_level.desc())
            .all()
        )
        return [self._format_task(t) for t in tasks]

    def get_today_tasks(self) -> List[Dict]:
        """مهام اليوم"""
        today_str = _today_str()
        tasks = (
            self.db.query(LawTasks)
            .filter(
                LawTasks.office_id == self.office_id,
                LawTasks.is_deleted == 0,
                func.date(LawTasks.due_at) == today_str,
            )
            .order_by(LawTasks.priority_level.desc())
            .all()
        )
        return [self._format_task(t) for t in tasks]

    def get_overdue_tasks(self) -> List[Dict]:
        """المهام المتأخرة (استحقت وقتها)"""
        today_str = _today_str()
        tasks = (
            self.db.query(LawTasks)
            .filter(
                LawTasks.office_id == self.office_id,
                LawTasks.is_deleted == 0,
                LawTasks.status_key.in_(["pending", "in_progress"]),
                LawTasks.due_at < today_str,
                LawTasks.due_at.isnot(None),
            )
            .order_by(LawTasks.due_at.asc())
            .all()
        )
        return [self._format_task(t) for t in tasks]

    def _format_task(self, t: LawTasks) -> Dict:
        return {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "due_at": t.due_at,
            "status": t.status_key,
            "priority": t.priority_level,
            "case_id": t.case_id,
            "created_at": t.created_at,
        }

    # ══════════════════════════════════════════
    # 6. البحث في القضايا
    # ══════════════════════════════════════════

    def search_cases(self, keyword: str) -> List[Dict]:
        """البحث في القضايا بكلمة مفتاحية"""
        kw = f"%{keyword.strip()}%"
        cases = (
            self.db.query(LawCases)
            .filter(
                LawCases.office_id == self.office_id,
                LawCases.is_deleted == 0,
                or_(
                    LawCases.title.ilike(kw),
                    LawCases.case_number.ilike(kw),
                    LawCases.summary.ilike(kw),
                    LawCases.description.ilike(kw),
                    LawCases.case_type_key.ilike(kw),
                ),
            )
            .order_by(LawCases.created_at.desc())
            .limit(20)
            .all()
        )
        return [
            {
                "case_number": c.case_number,
                "title": c.title,
                "status": c.status_key,
                "case_type": c.case_type_key,
                "open_date": c.open_date,
                "summary": c.summary,
            }
            for c in cases
        ]

    def search_cases_by_type(self, case_type: str) -> List[Dict]:
        """جلب القضايا حسب النوع"""
        cases = (
            self.db.query(LawCases)
            .filter(
                LawCases.office_id == self.office_id,
                LawCases.is_deleted == 0,
                LawCases.case_type_key.ilike(f"%{case_type}%"),
            )
            .order_by(LawCases.created_at.desc())
            .limit(20)
            .all()
        )
        return [
            {
                "case_number": c.case_number,
                "title": c.title,
                "status": c.status_key,
                "case_type": c.case_type_key,
            }
            for c in cases
        ]

    # ══════════════════════════════════════════
    # 7. إحصائيات الأداء
    # ══════════════════════════════════════════

    def get_performance_stats(self) -> Dict:
        """إحصائيات أداء المكتب الشاملة"""
        # إجمالي الأحكام
        total_judgments = (
            self.db.query(LawJudgments)
            .join(LawCases, LawJudgments.case_id == LawCases.id)
            .filter(
                LawJudgments.office_id == self.office_id,
                LawJudgments.is_deleted == 0,
            )
            .count()
        )

        # أحكام لصالح الموكل
        won = (
            self.db.query(LawJudgments)
            .filter(
                LawJudgments.office_id == self.office_id,
                LawJudgments.is_deleted == 0,
                LawJudgments.status_key.in_(["won", "approved", "favorable", "granted"]),
            )
            .count()
        )

        success_rate = round((won / total_judgments * 100), 1) if total_judgments > 0 else 0.0

        # إجمالي ساعات العمل
        hours_row = (
            self.db.query(func.sum(LawTimesheets.duration_hours))
            .filter(
                LawTimesheets.office_id == self.office_id,
                LawTimesheets.is_deleted == 0,
            )
            .scalar()
        )
        total_hours = float(hours_row or 0)

        # عدد الأطراف في القضايا
        total_parties = (
            self.db.query(LawParties)
            .filter(
                LawParties.office_id == self.office_id,
                LawParties.is_deleted == 0,
            )
            .count()
        )

        # قضايا منتهية
        cases_stats = self.get_cases_stats()

        return {
            "total_cases": cases_stats["total"],
            "open_cases": cases_stats["open"],
            "closed_cases": cases_stats["closed"],
            "total_judgments": total_judgments,
            "won_judgments": won,
            "success_rate": success_rate,
            "total_work_hours": round(total_hours, 1),
            "total_parties": total_parties,
        }

    # ══════════════════════════════════════════
    # 8. معلومات المكتب والمستخدمين
    # ══════════════════════════════════════════

    def get_office_users(self) -> List[Dict]:
        """أعضاء فريق المكتب"""
        users = (
            self.db.query(AccessProfiles)
            .filter(
                AccessProfiles.office_id == self.office_id,
                AccessProfiles.is_deleted == 0,
                AccessProfiles.is_active == 1,
            )
            .all()
        )
        return [
            {
                "id": u.id,
                "name": u.name,
                "role": u.role,
                "job_title": u.job_title,
                "phone": u.phone,
            }
            for u in users
        ]

    def get_upcoming_limitations(self, days: int = 30) -> List[Dict]:
        """المواعيد النهائية القادمة (التقادم والمهل)"""
        today_str = _today_str()
        end_date = (date.today() + timedelta(days=days)).isoformat()

        from database.models import LawLimitations
        lims = (
            self.db.query(LawLimitations)
            .filter(
                LawLimitations.office_id == self.office_id,
                LawLimitations.is_deleted == 0,
                LawLimitations.due_date >= today_str,
                LawLimitations.due_date <= end_date,
                LawLimitations.status_key == "active",
            )
            .order_by(LawLimitations.due_date.asc())
            .all()
        )

        result = []
        for lim in lims:
            days_left = (
                date.fromisoformat(lim.due_date) - date.today()
            ).days
            result.append({
                "id": lim.id,
                "title": lim.title,
                "limitation_type": lim.limitation_type_key,
                "due_date": lim.due_date,
                "days_left": days_left,
                "case_id": lim.case_id,
            })
        return result

    # ══════════════════════════════════════════
    # 9. الدالة الموحدة للإجابة
    # ══════════════════════════════════════════

    def answer_query(self, intent_type: str, entities: dict) -> Dict:
        """
        نقطة دخول موحدة تُجيب على أي استعلام بناءً على النية والكيانات.

        Args:
            intent_type: نوع النية من IntentDetector
            entities: الكيانات المستخرجة من السؤال

        Returns:
            Dict يحمل البيانات المطلوبة + metadata
        """
        try:
            time_ctx = entities.get("time_context")

            # ── القضايا ──
            if intent_type == "query_cases":
                data = self.get_cases_stats()
                return {"type": "cases_stats", "data": data, "success": True}

            # ── الجلسات ──
            elif intent_type == "query_hearings":
                if time_ctx == "today":
                    data = self.get_today_hearings()
                    return {"type": "today_hearings", "data": data, "success": True}
                elif time_ctx == "tomorrow":
                    data = self.get_tomorrow_hearings()
                    return {"type": "tomorrow_hearings", "data": data, "success": True}
                elif time_ctx == "this_week":
                    data = self.get_hearings_this_week()
                    return {"type": "week_hearings", "data": data, "success": True}
                elif time_ctx == "this_month":
                    data = self.get_hearings_this_month()
                    return {"type": "month_hearings", "data": data, "success": True}
                else:
                    # افتراضي: جلسات اليوم والمقبلة
                    today_h = self.get_today_hearings()
                    upcoming = self.get_upcoming_hearings(days=7)
                    return {
                        "type": "hearings",
                        "data": {"today": today_h, "upcoming": upcoming},
                        "success": True,
                    }

            # ── الموكلون ──
            elif intent_type == "query_clients":
                if "client_name" in entities:
                    clients = self.search_clients(entities["client_name"])
                    return {"type": "client_search", "data": clients, "success": True}
                else:
                    data = self.get_clients_stats()
                    return {"type": "clients_stats", "data": data, "success": True}

            # ── المالية ──
            elif intent_type == "query_finance":
                data = self.get_finance_summary()
                return {"type": "finance_summary", "data": data, "success": True}

            # ── المهام ──
            elif intent_type == "query_tasks":
                if time_ctx == "today":
                    data = self.get_today_tasks()
                    return {"type": "today_tasks", "data": data, "success": True}
                else:
                    data = self.get_pending_tasks()
                    return {"type": "pending_tasks", "data": data, "success": True}

            # ── البحث في القضايا ──
            elif intent_type == "search_case":
                case_number = entities.get("case_number")
                if case_number:
                    case = self.get_case_by_number(case_number)
                    if case:
                        return {"type": "case_detail", "data": case, "success": True}
                    else:
                        return {"type": "not_found", "data": None, "success": False,
                                "message": f"لم يُعثر على القضية رقم {case_number}"}

                case_type = entities.get("case_type")
                numbers = entities.get("numbers", [])
                kw = case_type or (str(numbers[0]) if numbers else "")

                if kw:
                    data = self.search_cases(kw)
                    return {"type": "case_search", "data": data, "success": True}
                else:
                    data = self.get_recent_cases(limit=10)
                    return {"type": "recent_cases", "data": data, "success": True}

            # ── الإحصائيات ──
            elif intent_type == "analyze_stats":
                data = self.get_performance_stats()
                return {"type": "performance_stats", "data": data, "success": True}

            # ── غير معروف ──
            else:
                return {
                    "type": "no_data",
                    "data": None,
                    "success": False,
                    "message": "لا توجد بيانات لهذا الاستعلام",
                }

        except Exception as exc:
            return {
                "type": "error",
                "data": None,
                "success": False,
                "message": f"خطأ في استعلام قاعدة البيانات: {str(exc)}",
            }
