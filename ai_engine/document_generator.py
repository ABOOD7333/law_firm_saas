"""
مولّد المستندات القانونية اليمنية
يُنشئ المستندات القانونية من القوالب الجاهزة بعد ملء البيانات
"""
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from .knowledge_base.document_templates import ALL_TEMPLATES, TEMPLATE_KEYWORDS


class DocumentGenerator:
    """مولّد المستندات القانونية"""

    HIJRI_MONTHS = [
        "محرم", "صفر", "ربيع الأول", "ربيع الثاني",
        "جمادى الأولى", "جمادى الثانية", "رجب", "شعبان",
        "رمضان", "شوال", "ذو القعدة", "ذو الحجة"
    ]

    # قائمة جميع الوثائق مع وصفها
    DOCUMENTS_LIST = [
        {"code": "civil_lawsuit",        "name": "صحيفة دعوى مدنية",       "icon": "⚖️"},
        {"code": "defense_memo",         "name": "مذكرة دفاع",              "icon": "🛡️"},
        {"code": "sale_contract",        "name": "عقد بيع",                 "icon": "🏠"},
        {"code": "lease_contract",       "name": "عقد إيجار",               "icon": "🔑"},
        {"code": "partnership_contract", "name": "عقد شراكة تجارية",        "icon": "🤝"},
        {"code": "power_of_attorney",    "name": "وكالة قانونية",           "icon": "📋"},
        {"code": "legal_warning",        "name": "إنذار قانوني",            "icon": "⚠️"},
        {"code": "appeal",               "name": "طعن استئناف",             "icon": "📄"},
        {"code": "execution_request",    "name": "طلب تنفيذ حكم",           "icon": "🔨"},
        {"code": "employment_contract",  "name": "عقد عمل",                 "icon": "💼"},
        {"code": "debt_acknowledgment",  "name": "إقرار بدين",              "icon": "💰"},
        {"code": "settlement_agreement", "name": "اتفاقية تسوية ودية",      "icon": "🕊️"},
        {"code": "hearing_postponement", "name": "طلب تأجيل جلسة",         "icon": "📅"},
        {"code": "legal_invoice",        "name": "فاتورة أتعاب محاماة",     "icon": "🧾"},
        {"code": "case_statement",       "name": "ملخص وكشف حساب قضية",    "icon": "📊"},
    ]

    def detect_document_type(self, text: str) -> Optional[str]:
        """يكتشف نوع المستند المطلوب من النص"""
        text = text.lower()
        for keyword, doc_code in TEMPLATE_KEYWORDS.items():
            if keyword in text:
                return doc_code
        return None

    def get_document_info(self, doc_code: str) -> Optional[Dict]:
        """يُعيد معلومات القالب"""
        return ALL_TEMPLATES.get(doc_code)

    def get_required_fields(self, doc_code: str) -> List[str]:
        """يُعيد قائمة الحقول المطلوبة للمستند"""
        template = ALL_TEMPLATES.get(doc_code)
        if not template:
            return []
        return template.get("required_fields", [])

    def get_fields_questions(self, doc_code: str) -> str:
        """يُعيد أسئلة لجمع البيانات المطلوبة"""
        template = ALL_TEMPLATES.get(doc_code)
        if not template:
            return "نوع المستند غير معروف."

        questions = {
            "plaintiff_name": "اسم المدعي (صاحب الدعوى)",
            "plaintiff_id": "رقم هوية المدعي",
            "plaintiff_address": "عنوان المدعي",
            "defendant_name": "اسم المدعى عليه",
            "defendant_id": "رقم هوية المدعى عليه",
            "defendant_address": "عنوان المدعى عليه",
            "court_name": "اسم المحكمة",
            "claim_amount": "قيمة المطالبة (بالأرقام)",
            "claim_details": "تفاصيل الدعوى والطلبات",
            "lawyer_name": "اسم المحامي",
            "date": "التاريخ (سيُملأ تلقائياً)",
            "seller_name": "اسم البائع",
            "seller_id": "رقم هوية البائع",
            "buyer_name": "اسم المشتري",
            "buyer_id": "رقم هوية المشتري",
            "property_description": "وصف العقار أو المنقول المباع",
            "price": "السعر (بالأرقام)",
            "payment_method": "طريقة الدفع (نقداً / بالتقسيط)",
            "delivery_date": "تاريخ التسليم",
            "landlord_name": "اسم المؤجر",
            "landlord_id": "رقم هوية المؤجر",
            "tenant_name": "اسم المستأجر",
            "tenant_id": "رقم هوية المستأجر",
            "property_address": "عنوان العقار",
            "monthly_rent": "الأجرة الشهرية",
            "start_date": "تاريخ البداية",
            "end_date": "تاريخ الانتهاء",
            "deposit": "مبلغ التأمين",
            "client_name": "اسم الموكل",
            "client_id": "رقم هوية الموكل",
            "client_address": "عنوان الموكل",
            "lawyer_license": "رقم ترخيص المحامي",
            "case_description": "وصف القضية أو الغرض من الوكالة",
            "powers": "الصلاحيات الممنوحة (التقاضي، الاستئناف، التنفيذ...)",
            "sender_name": "اسم مُرسل الإنذار",
            "sender_id": "رقم هويته",
            "receiver_name": "اسم مستقبل الإنذار",
            "receiver_address": "عنوانه",
            "warning_subject": "موضوع الإنذار",
            "warning_details": "تفاصيل الإنذار",
            "required_action": "الإجراء المطلوب",
            "deadline": "المهلة المحددة",
            "case_number": "رقم القضية",
            "judgment_date": "تاريخ الحكم",
            "appeal_grounds": "أسباب الاستئناف",
            "requests": "الطلبات من محكمة الاستئناف",
            "appellant_name": "اسم المستأنف",
            "appellee_name": "اسم المستأنف ضده",
            "judgment_details": "مضمون الحكم المراد تنفيذه",
            "debtor_name": "اسم المنفذ ضده (المدين)",
            "debtor_address": "عنوانه",
            "creditor_name": "اسم الدائن (طالب التنفيذ)",
            "execution_amount": "مبلغ التنفيذ",
            "employer_name": "اسم صاحب العمل",
            "employer_id": "رقم سجله التجاري",
            "employee_name": "اسم الموظف",
            "employee_id": "رقم هويته",
            "job_title": "المسمى الوظيفي",
            "salary": "الراتب الشهري",
            "contract_duration": "مدة العقد",
            "work_hours": "ساعات العمل اليومية",
            "debt_amount": "مبلغ الدين",
            "debt_reason": "سبب الدين",
            "payment_deadline": "موعد السداد",
            "witnesses": "أسماء الشهود",
            "dispute_description": "وصف النزاع",
            "settlement_terms": "شروط التسوية",
            "settlement_amount": "مبلغ التسوية (إن وجد)",
            "hearing_date": "موعد الجلسة المراد تأجيلها",
            "postponement_reason": "سبب طلب التأجيل",
            "services": "الخدمات القانونية المقدمة",
            "total_amount": "إجمالي الأتعاب",
            "office_name": "اسم المكتب",
            "case_type": "نوع القضية",
            "current_status": "الحالة الراهنة للقضية",
            "key_dates": "أهم المواعيد والإجراءات",
            "city": "المدينة",
            "partner1_name": "اسم الشريك الأول",
            "partner1_id": "رقم هويته",
            "partner1_share": "نسبة حصته %",
            "partner2_name": "اسم الشريك الثاني",
            "partner2_id": "رقم هويته",
            "partner2_share": "نسبة حصته %",
            "business_name": "الاسم التجاري للشراكة",
            "business_type": "نوع النشاط التجاري",
            "capital": "رأس المال الإجمالي",
            "case_number_text": "رقم القضية",
            "debtor_id": "رقم هوية المدين",
            "debt_amount_words": "المبلغ كتابةً",
            "witness1": "الشاهد الأول",
            "witness2": "الشاهد الثاني",
            "party1_name": "اسم الطرف الأول",
            "party1_id": "رقم هويته",
            "party2_name": "اسم الطرف الثاني",
            "party2_id": "رقم هويته",
            "facts": "وقائع القضية",
            "defense_points": "نقاط الدفاع القانونية",
            "opponent_name": "اسم الخصم",
            "is_general": "عامة / خاصة",
            "lawyer_notes": "ملاحظات المحامي",
        }

        fields = template.get("required_fields", [])
        lines = [f"✅ **{template['name']}** - أحتاج المعلومات التالية:\n"]
        for i, field in enumerate(fields, 1):
            label = questions.get(field, field)
            if field != "date":  # التاريخ يُملأ تلقائياً
                lines.append(f"**{i}.** {label}")

        lines.append("\nأرسل لي هذه المعلومات وسأُنشئ المستند فوراً! 📄")
        return "\n".join(lines)

    def generate(self, doc_code: str, data: Dict) -> Tuple[bool, str]:
        """
        يُنشئ المستند بعد ملء البيانات
        يُعيد (نجاح, المستند أو رسالة الخطأ)
        """
        template_info = ALL_TEMPLATES.get(doc_code)
        if not template_info:
            return False, "❌ نوع المستند غير معروف."

        # إضافة التاريخ تلقائياً
        if "date" not in data or not data["date"]:
            data["date"] = datetime.now().strftime("%Y/%m/%d")

        # التحقق من الحقول المطلوبة
        required = template_info.get("required_fields", [])
        missing = []
        for field in required:
            if field not in data or not data.get(field):
                if field not in ["date", "facts", "lawyer_notes", "witnesses",
                                  "witness1", "witness2", "debt_amount_words"]:
                    missing.append(field)

        if missing:
            return False, f"⚠️ يرجى إكمال البيانات التالية: {', '.join(missing)}"

        try:
            # إضافة المبلغ كتابةً إن وجد
            if "debt_amount" in data and "debt_amount_words" not in data:
                data["debt_amount_words"] = self._amount_to_words(
                    str(data.get("debt_amount", ""))
                )

            # ملء القالب
            document = template_info["template"].format_map(
                {k: data.get(k, f"[{k}]") for k in
                 [f.replace("{", "").replace("}", "")
                  for f in template_info["template"].split("{")[1:]
                  if "}" in f]}
            )
            return True, document
        except Exception as e:
            # محاولة بديلة
            try:
                template_str = template_info["template"]
                for key, value in data.items():
                    template_str = template_str.replace(f"{{{key}}}", str(value))
                return True, template_str
            except Exception as e2:
                return False, f"❌ خطأ في إنشاء المستند: {str(e2)}"

    def get_documents_menu(self) -> str:
        """يُعيد قائمة بكل المستندات المتاحة"""
        lines = ["📋 **المستندات القانونية المتاحة:**\n"]
        for i, doc in enumerate(self.DOCUMENTS_LIST, 1):
            lines.append(f"{doc['icon']} **{i}.** {doc['name']}")
        lines.append("\nاكتب اسم المستند الذي تريده وسأساعدك في إنشائه!")
        return "\n".join(lines)

    def _amount_to_words(self, amount_str: str) -> str:
        """يحوّل الرقم إلى كلمات بسيطة"""
        try:
            amount = int(amount_str.replace(",", ""))
            if amount < 1000:
                return f"{amount} ريال"
            elif amount < 1_000_000:
                thousands = amount // 1000
                remainder = amount % 1000
                result = f"{thousands} ألف"
                if remainder:
                    result += f" و{remainder}"
                return result + " ريال يمني"
            else:
                millions = amount // 1_000_000
                remainder = amount % 1_000_000
                result = f"{millions} مليون"
                if remainder:
                    result += f" و{remainder // 1000} ألف"
                return result + " ريال يمني"
        except Exception:
            return amount_str + " ريال يمني"
