"""
منشئ الردود - يبني رداً نصياً منظماً ومنسقاً باللغة العربية
Response Builder - Builds structured, formatted Arabic text responses
"""
from typing import Dict, List, Optional
from datetime import date, datetime


# ─────────────────────────────────────────────
# أيام الأسبوع والأشهر بالعربية
# ─────────────────────────────────────────────
ARABIC_WEEKDAYS = {
    0: "الإثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد",
}

ARABIC_MONTHS = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

STATUS_LABELS = {
    "open": "مفتوحة", "active": "نشطة", "draft": "مسودة",
    "in_progress": "قيد التنفيذ", "closed": "مغلقة",
    "completed": "مكتملة", "done": "منتهية",
    "pending": "معلقة", "paid": "مدفوعة", "cancelled": "ملغاة",
    "won": "فوز", "lost": "خسارة", "favorable": "مواتية",
}

PRIORITY_LABELS = {
    1: "منخفضة", 2: "عادية", 3: "عالية", 4: "عاجلة", 5: "حرجة",
}


def _format_date(date_str: Optional[str]) -> str:
    """تحويل تاريخ ISO إلى صيغة عربية مقروءة"""
    if not date_str:
        return "غير محدد"
    try:
        d = date.fromisoformat(date_str[:10])
        weekday = ARABIC_WEEKDAYS.get(d.weekday(), "")
        month_name = ARABIC_MONTHS.get(d.month, "")
        return f"{weekday} {d.day} {month_name} {d.year}"
    except (ValueError, TypeError):
        return date_str


def _format_datetime(dt_str: Optional[str]) -> str:
    """تحويل datetime إلى صيغة عربية"""
    if not dt_str:
        return "غير محدد"
    try:
        dt = datetime.fromisoformat(dt_str[:19])
        d = dt.date()
        month_name = ARABIC_MONTHS.get(d.month, "")
        time_part = dt.strftime("%H:%M")
        return f"{d.day} {month_name} {d.year} الساعة {time_part}"
    except (ValueError, TypeError):
        return dt_str


def _format_time(dt_str: Optional[str]) -> str:
    """استخراج الوقت فقط"""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str[:19])
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def _format_currency(amount: float) -> str:
    """تنسيق المبالغ المالية بالريال اليمني"""
    if amount == 0:
        return "صفر"
    formatted = f"{amount:,.0f}"
    return f"{formatted} ر.ي"


def _status_label(key: str) -> str:
    return STATUS_LABELS.get(key, key or "غير محدد")


def _priority_label(level: int) -> str:
    return PRIORITY_LABELS.get(level, "عادية")


class ResponseBuilder:
    """
    يبني ردوداً نصية منسقة وجميلة باللغة العربية
    لكل أنواع الاستعلامات في مكتب المحاماة.
    """

    def build_response(
        self,
        intent_type: str,
        db_data: Optional[Dict],
        search_results: Optional[List],
        entities: dict,
    ) -> str:
        """
        يبني الرد المناسب بناءً على نوع الاستعلام والبيانات.

        Args:
            intent_type: نوع النية
            db_data: بيانات قاعدة البيانات (من DBQueryEngine)
            search_results: نتائج البحث القانوني (من LegalSearchEngine)
            entities: الكيانات المستخرجة من السؤال

        Returns:
            str: نص الرد المنسق
        """
        try:
            # ─── ردود لا تحتاج بيانات ───
            if intent_type == "greeting":
                return self._build_greeting_response()

            if intent_type == "help":
                return self._build_help_response()

            # ─── ردود قاعدة البيانات ───
            if db_data:
                dtype = db_data.get("type", "")
                data = db_data.get("data")

                if not db_data.get("success") and dtype != "not_found":
                    return self._build_error_response(
                        db_data.get("message", "حدث خطأ غير متوقع")
                    )

                if dtype == "cases_stats":
                    return self._format_cases_response(data)

                elif dtype in ("today_hearings", "tomorrow_hearings",
                               "week_hearings", "month_hearings", "hearings"):
                    return self._format_hearings_response(data, dtype)

                elif dtype == "clients_stats":
                    return self._format_clients_stats_response(data)

                elif dtype == "client_search":
                    return self._format_client_search_response(data)

                elif dtype == "finance_summary":
                    return self._format_finance_response(data)

                elif dtype in ("pending_tasks", "today_tasks"):
                    return self._format_tasks_response(data, dtype)

                elif dtype == "case_detail":
                    return self._format_case_detail_response(data)

                elif dtype == "case_search":
                    return self._format_case_search_response(data)

                elif dtype == "recent_cases":
                    return self._format_recent_cases_response(data)

                elif dtype == "performance_stats":
                    return self._format_stats_response(data)

                elif dtype == "not_found":
                    return f"🔍 {db_data.get('message', 'لم يتم العثور على نتائج.')}"

            # ─── ردود البحث القانوني ───
            if search_results is not None:
                if intent_type == "search_law":
                    return self._format_law_search_response(search_results, entities)

            # ─── الاستشارة القانونية ───
            if intent_type == "legal_advice":
                return self._build_legal_advice_intro()

            # ─── إنشاء وثيقة ───
            if intent_type == "generate_document":
                doc_type = entities.get("document_type", "وثيقة قانونية")
                return self._build_document_generation_response(doc_type)

            # ─── غير معروف ───
            return self._build_unknown_response()

        except Exception as exc:
            return self._build_error_response(str(exc))

    # ══════════════════════════════════════════
    # 1. القضايا
    # ══════════════════════════════════════════

    def _format_cases_response(self, data: Dict) -> str:
        if not data:
            return "⚠️ لا تتوفر بيانات عن القضايا حالياً."

        total = data.get("total", 0)
        open_c = data.get("open", 0)
        closed_c = data.get("closed", 0)
        this_month = data.get("this_month", 0)
        this_year = data.get("this_year", 0)
        added_today = data.get("added_today", 0)
        by_type = data.get("by_type", {})

        lines = [
            "📂 **إحصائيات القضايا**",
            "─────────────────────────",
            f"📊 إجمالي القضايا: **{total}** قضية",
            f"🟢 القضايا المفتوحة: **{open_c}**",
            f"✅ القضايا المنتهية: **{closed_c}**",
            f"📅 هذا الشهر: **{this_month}** قضية جديدة",
            f"📆 هذا العام: **{this_year}** قضية",
        ]

        if added_today > 0:
            lines.append(f"🆕 أُضيف اليوم: **{added_today}** قضية")

        if by_type:
            lines.append("\n**تصنيف القضايا حسب النوع:**")
            for case_type, count in by_type.items():
                label = case_type or "غير محدد"
                lines.append(f"  • {label}: {count}")

        return "\n".join(lines)

    def _format_case_detail_response(self, data: Dict) -> str:
        if not data:
            return "⚠️ لم يتم العثور على بيانات القضية."

        lines = [
            f"📁 **تفاصيل القضية رقم {data.get('case_number', '---')}**",
            "─────────────────────────",
            f"📌 العنوان: {data.get('title', 'غير محدد')}",
            f"🔖 النوع: {data.get('case_type', 'غير محدد')}",
            f"🔴 الحالة: {_status_label(data.get('status', ''))}",
            f"📅 تاريخ الفتح: {_format_date(data.get('open_date'))}",
        ]

        if data.get("close_date"):
            lines.append(f"🏁 تاريخ الإغلاق: {_format_date(data.get('close_date'))}")

        if data.get("estimated_fee"):
            lines.append(f"💰 الأتعاب المقدَّرة: {_format_currency(data['estimated_fee'])}")

        if data.get("claim_amount"):
            lines.append(f"💵 قيمة المطالبة: {_format_currency(data['claim_amount'])}")

        if data.get("summary"):
            lines.append(f"\n📝 ملخص: {data['summary']}")

        return "\n".join(lines)

    def _format_recent_cases_response(self, data: List) -> str:
        if not data:
            return "📂 لا توجد قضايا حديثة."

        lines = [f"📂 **آخر {len(data)} قضايا مضافة:**", "─────────────────────────"]
        for i, c in enumerate(data, 1):
            status = _status_label(c.get("status", ""))
            case_type = c.get("case_type") or "غير محدد"
            lines.append(
                f"{i}. [{c.get('case_number', '---')}] {c.get('title', '---')} "
                f"| {case_type} | {status}"
            )

        return "\n".join(lines)

    def _format_case_search_response(self, data: List) -> str:
        if not data:
            return "🔍 لم يتم العثور على قضايا تتطابق مع بحثك."

        lines = [
            f"🔍 **نتائج البحث - {len(data)} قضية:**",
            "─────────────────────────",
        ]
        for i, c in enumerate(data, 1):
            status = _status_label(c.get("status", ""))
            lines.append(
                f"{i}. **{c.get('case_number', '---')}** - {c.get('title', '---')}"
            )
            lines.append(f"   النوع: {c.get('case_type') or 'غير محدد'} | الحالة: {status}")
            if c.get("summary"):
                lines.append(f"   {c['summary'][:80]}...")

        return "\n".join(lines)

    # ══════════════════════════════════════════
    # 2. الجلسات
    # ══════════════════════════════════════════

    def _format_hearings_response(self, data, dtype: str) -> str:
        # تحديد العنوان
        titles = {
            "today_hearings": "🏛️ **جلسات اليوم**",
            "tomorrow_hearings": "🏛️ **جلسات الغد**",
            "week_hearings": "🏛️ **جلسات هذا الأسبوع**",
            "month_hearings": "🏛️ **جلسات هذا الشهر**",
            "hearings": "🏛️ **الجلسات**",
        }
        title = titles.get(dtype, "🏛️ **الجلسات**")

        # معالجة البيانات المركبة (today + upcoming)
        if dtype == "hearings" and isinstance(data, dict):
            today_list = data.get("today", [])
            upcoming_list = data.get("upcoming", [])
            lines = [title, "─────────────────────────"]

            if today_list:
                lines.append("\n**اليوم:**")
                lines.extend(self._render_hearing_list(today_list))
            else:
                lines.append("• لا توجد جلسات اليوم")

            if upcoming_list:
                lines.append("\n**الجلسات القادمة (7 أيام):**")
                lines.extend(self._render_hearing_list(upcoming_list))

            return "\n".join(lines)

        # قائمة بسيطة
        hearings = data if isinstance(data, list) else []
        lines = [title, "─────────────────────────"]

        if not hearings:
            lines.append("📭 لا توجد جلسات مجدولة.")
        else:
            lines.append(f"📋 إجمالي: **{len(hearings)}** جلسة\n")
            lines.extend(self._render_hearing_list(hearings))

        return "\n".join(lines)

    def _render_hearing_list(self, hearings: List) -> List[str]:
        """يصيّر قائمة الجلسات"""
        lines = []
        for h in hearings:
            time_part = _format_time(h.get("hearing_at"))
            date_part = _format_date(h.get("hearing_at"))
            case_num = h.get("case_number", "")
            case_title = h.get("case_title", "")
            status = _status_label(h.get("status", ""))

            lines.append(f"🕐 {time_part} | {date_part}")
            lines.append(f"   📁 القضية: [{case_num}] {case_title}")
            lines.append(f"   عنوان الجلسة: {h.get('title', '')}")
            lines.append(f"   الحالة: {status}")

            if h.get("next_hearing_date"):
                lines.append(
                    f"   📅 الجلسة التالية: {_format_date(h.get('next_hearing_date'))}"
                )
            lines.append("")  # سطر فراغ

        return lines

    # ══════════════════════════════════════════
    # 3. الموكلون
    # ══════════════════════════════════════════

    def _format_clients_stats_response(self, data: Dict) -> str:
        if not data:
            return "⚠️ لا تتوفر بيانات عن الموكلين."

        lines = [
            "👤 **إحصائيات الموكلين**",
            "─────────────────────────",
            f"👥 إجمالي الموكلين: **{data.get('total', 0)}** موكل",
            f"📅 مضافون هذا الشهر: **{data.get('this_month', 0)}**",
        ]
        return "\n".join(lines)

    def _format_client_search_response(self, data: List) -> str:
        if not data:
            return "🔍 لم يتم العثور على موكلين بهذا الاسم."

        lines = [
            f"👤 **نتائج البحث عن الموكل - {len(data)} نتيجة:**",
            "─────────────────────────",
        ]
        for c in data:
            lines.append(f"• **{c.get('name', '---')}**")
            if c.get("phone"):
                lines.append(f"  📞 {c['phone']}")
            if c.get("email"):
                lines.append(f"  📧 {c['email']}")
            if c.get("case_number"):
                lines.append(f"  📁 القضية: {c['case_number']}")
            if c.get("national_id"):
                lines.append(f"  🪪 رقم الهوية: {c['national_id']}")
            lines.append("")

        return "\n".join(lines)

    # ══════════════════════════════════════════
    # 4. المالية
    # ══════════════════════════════════════════

    def _format_finance_response(self, data: Dict) -> str:
        if not data:
            return "⚠️ لا تتوفر بيانات مالية."

        net = data.get("net_profit", 0)
        net_symbol = "📈" if net >= 0 else "📉"
        net_label = "صافي الربح" if net >= 0 else "صافي الخسارة"

        lines = [
            "💰 **الملخص المالي للمكتب**",
            "─────────────────────────",
            f"✅ إجمالي الإيرادات المحصَّلة: **{_format_currency(data.get('total_income', 0))}**",
            f"⏳ إيرادات معلقة: **{_format_currency(data.get('pending_income', 0))}**",
            f"💸 إجمالي المصروفات: **{_format_currency(data.get('total_expenses', 0))}**",
            f"{net_symbol} {net_label}: **{_format_currency(abs(net))}**",
            "─────────────────────────",
            f"📅 إيرادات هذا الشهر: **{_format_currency(data.get('this_month_income', 0))}**",
            f"📆 إيرادات هذا العام: **{_format_currency(data.get('this_year_income', 0))}**",
        ]
        return "\n".join(lines)

    # ══════════════════════════════════════════
    # 5. المهام
    # ══════════════════════════════════════════

    def _format_tasks_response(self, data: List, dtype: str) -> str:
        title = "📋 **مهام اليوم**" if dtype == "today_tasks" else "📋 **المهام المعلقة**"
        lines = [title, "─────────────────────────"]

        if not data:
            lines.append("✅ لا توجد مهام معلقة. عمل رائع!")
            return "\n".join(lines)

        lines.append(f"📌 إجمالي: **{len(data)}** مهمة\n")

        for t in data:
            priority = _priority_label(t.get("priority", 2))
            status = _status_label(t.get("status", "pending"))
            due = _format_date(t.get("due_at")) if t.get("due_at") else "—"

            priority_icon = {
                "حرجة": "🔴", "عاجلة": "🟠",
                "عالية": "🟡", "عادية": "🔵", "منخفضة": "⚪",
            }.get(priority, "🔵")

            lines.append(f"{priority_icon} **{t.get('title', '---')}**")
            lines.append(f"   الأولوية: {priority} | الحالة: {status}")
            if t.get("due_at"):
                lines.append(f"   ⏰ الاستحقاق: {due}")
            if t.get("description"):
                desc = t["description"][:80]
                lines.append(f"   📝 {desc}")
            lines.append("")

        return "\n".join(lines)

    # ══════════════════════════════════════════
    # 6. البحث القانوني
    # ══════════════════════════════════════════

    def _format_law_search_response(self, results: List, entities: dict) -> str:
        if not results:
            return (
                "🔍 لم يتم العثور على نص قانوني مطابق لسؤالك.\n\n"
                "💡 **اقتراحات:**\n"
                "• حدد اسم القانون ورقم المادة (مثال: المادة 55 من قانون العمل)\n"
                "• استخدم كلمات مفتاحية أوضح"
            )

        lines = ["⚖️ **نتائج البحث القانوني**", "─────────────────────────"]

        for i, result in enumerate(results, 1):
            law = result.get("law", "")
            article = result.get("article", "")
            title = result.get("title", "")
            text = result.get("text", "")
            year = result.get("year", "")
            score = result.get("score", 0)

            lines.append(f"**{i}. {law} - المادة ({article})**")
            if year:
                lines.append(f"   📋 رقم القانون: {result.get('law_number', '')} لعام {year}")
            if title:
                lines.append(f"   📌 **{title}**")
            lines.append(f"   📜 {text}")

            # نسبة التطابق
            if i == 1 and score > 0:
                pct = min(int(score * 20), 100)  # تطبيع تقريبي
                lines.append(f"   ✨ درجة التطابق: {pct}%")

            lines.append("")

        lines.append("─────────────────────────")
        lines.append("⚠️ *هذه المعلومات للاسترشاد فقط، يُنصح بمراجعة المحامي المختص.*")
        return "\n".join(lines)

    # ══════════════════════════════════════════
    # 7. الإحصائيات والأداء
    # ══════════════════════════════════════════

    def _format_stats_response(self, data: Dict) -> str:
        if not data:
            return "⚠️ لا تتوفر إحصائيات أداء."

        success_rate = data.get("success_rate", 0)
        rate_icon = "🏆" if success_rate >= 70 else ("👍" if success_rate >= 50 else "📊")

        lines = [
            "📊 **إحصائيات أداء المكتب**",
            "─────────────────────────",
            f"📂 إجمالي القضايا: **{data.get('total_cases', 0)}**",
            f"🟢 القضايا المفتوحة: **{data.get('open_cases', 0)}**",
            f"✅ القضايا المنتهية: **{data.get('closed_cases', 0)}**",
            "",
            f"⚖️ إجمالي الأحكام: **{data.get('total_judgments', 0)}**",
            f"🏆 أحكام لصالح الموكل: **{data.get('won_judgments', 0)}**",
            f"{rate_icon} نسبة النجاح: **{success_rate}%**",
            "",
            f"⏱️ إجمالي ساعات العمل: **{data.get('total_work_hours', 0):,.1f}** ساعة",
            f"👥 إجمالي الأطراف: **{data.get('total_parties', 0)}**",
        ]
        return "\n".join(lines)

    # ══════════════════════════════════════════
    # 8. ردود ثابتة
    # ══════════════════════════════════════════

    def _build_greeting_response(self, name: str = "") -> str:
        today = date.today()
        weekday = ARABIC_WEEKDAYS.get(today.weekday(), "")
        month = ARABIC_MONTHS.get(today.month, "")
        date_str = f"{weekday} {today.day} {month} {today.year}"

        greeting = f"مرحباً {'بك ' + name if name else 'بك'}! 👋"

        return (
            f"{greeting}\n\n"
            f"📅 اليوم: **{date_str}**\n\n"
            "أنا مساعدك القانوني الذكي، يمكنني مساعدتك في:\n"
            "• 📂 الاستعلام عن القضايا والجلسات\n"
            "• 👤 إدارة بيانات الموكلين\n"
            "• 💰 الملخص المالي للمكتب\n"
            "• ⚖️ البحث في القوانين اليمنية\n"
            "• 📋 متابعة المهام والواجبات\n\n"
            "كيف يمكنني مساعدتك اليوم؟ 😊"
        )

    def _build_help_response(self) -> str:
        return (
            "🤖 **مساعد المكتب الذكي - دليل الاستخدام**\n"
            "─────────────────────────\n\n"
            "**📂 استعلامات القضايا:**\n"
            "• كم عدد القضايا؟\n"
            "• القضايا المفتوحة\n"
            "• قضايا هذا الشهر\n"
            "• ابحث عن قضية رقم 2024/001\n\n"
            "**🏛️ الجلسات:**\n"
            "• جلسات اليوم\n"
            "• جلسات غداً\n"
            "• جلسات هذا الأسبوع\n\n"
            "**👤 الموكلون:**\n"
            "• عدد الموكلين\n"
            "• ابحث عن موكل محمد علي\n\n"
            "**💰 المالية:**\n"
            "• الملخص المالي\n"
            "• الإيرادات هذا الشهر\n"
            "• إجمالي المصروفات\n\n"
            "**⚖️ البحث القانوني:**\n"
            "• المادة 55 من قانون العمل\n"
            "• عقوبة السرقة في القانون اليمني\n"
            "• ما حكم الطلاق في قانون الأحوال الشخصية\n\n"
            "**📋 المهام:**\n"
            "• المهام المعلقة\n"
            "• مهام اليوم\n\n"
            "**📊 الإحصائيات:**\n"
            "• نسبة النجاح\n"
            "• إحصائيات المكتب\n\n"
            "─────────────────────────\n"
            "💡 يمكنك السؤال بأسلوبك الطبيعي وسأفهمك!"
        )

    def _build_legal_advice_intro(self) -> str:
        return (
            "⚖️ **استشارة قانونية**\n"
            "─────────────────────────\n\n"
            "يسعدني تقديم المساعدة القانونية. للحصول على إجابة دقيقة، "
            "يُرجى توضيح:\n\n"
            "1️⃣ **موضوع الاستشارة** (عقود / أسرة / جنائي / عمالي...)\n"
            "2️⃣ **القانون المعني** إن كنت تعلمه\n"
            "3️⃣ **تفاصيل الحالة** باختصار\n\n"
            "يمكنك أيضاً البحث مباشرةً عن مادة قانونية:\n"
            "*مثال: المادة 30 من قانون العمل*\n\n"
            "⚠️ *تنبيه: هذه المعلومات للاسترشاد فقط ولا تُغني عن استشارة محامٍ.*"
        )

    def _build_document_generation_response(self, doc_type: str) -> str:
        return (
            f"📄 **إنشاء {doc_type}**\n"
            "─────────────────────────\n\n"
            f"لإنشاء **{doc_type}** ، يُرجى تزويدي بالمعلومات التالية:\n\n"
            "1️⃣ **بيانات الأطراف** (الأسماء والمعرّفات)\n"
            "2️⃣ **موضوع الوثيقة** وتفاصيله\n"
            "3️⃣ **التاريخ والمبالغ** إن وجدت\n"
            "4️⃣ **الشروط الخاصة** إن كان هناك متطلبات محددة\n\n"
            "بعد توفير هذه المعلومات سأقوم بصياغة الوثيقة كاملةً وفق "
            "أحكام القانون اليمني."
        )

    def _build_error_response(self, error: str) -> str:
        return (
            "⚠️ **حدث خطأ**\n"
            "─────────────────────────\n"
            f"{error}\n\n"
            "يُرجى المحاولة مرةً أخرى أو التواصل مع الدعم الفني."
        )

    def _build_unknown_response(self) -> str:
        return (
            "🤔 لم أتمكن من فهم سؤالك بشكل كامل.\n\n"
            "💡 **جرّب أحد هذه الأوامر:**\n"
            "• كم عدد القضايا المفتوحة؟\n"
            "• ما جلسات اليوم؟\n"
            "• الملخص المالي\n"
            "• المادة 55 من قانون العمل\n"
            "• المهام المعلقة\n\n"
            "أو اكتب **مساعدة** لعرض دليل الاستخدام الكامل."
        )
