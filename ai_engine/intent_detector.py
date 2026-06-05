"""
كاشف النية - يحلل سؤال المستخدم ويحدد ماذا يريد
Intent Detector - Analyzes user questions and determines intent
"""
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple


@dataclass
class Intent:
    type: str                          # نوع النية
    confidence: float                  # درجة الثقة 0-1
    entities: Dict                     # الكيانات المستخرجة
    sub_type: Optional[str] = None     # النوع الفرعي
    law_name: Optional[str] = None     # اسم القانون
    article_number: Optional[str] = None  # رقم المادة
    document_type: Optional[str] = None   # نوع الوثيقة


# ─────────────────────────────────────────────
# أنواع النيات المدعومة
# ─────────────────────────────────────────────
INTENT_TYPES = {
    "query_cases":       "استعلام عن القضايا",
    "query_hearings":    "استعلام عن الجلسات",
    "query_clients":     "استعلام عن الموكلين",
    "query_finance":     "استعلام مالي",
    "query_tasks":       "استعلام عن المهام",
    "search_law":        "بحث في القانون",
    "generate_document": "إنشاء وثيقة",
    "analyze_stats":     "تحليل إحصائي",
    "search_case":       "بحث في القضايا",
    "legal_advice":      "استشارة قانونية",
    "greeting":          "تحية",
    "help":              "مساعدة",
    "unknown":           "غير معروف",
}

# ─────────────────────────────────────────────
# قوائم الكلمات المفتاحية
# ─────────────────────────────────────────────
GREETING_WORDS = [
    "مرحبا", "مرحباً", "السلام", "أهلا", "أهلاً", "هلا",
    "صباح", "مساء", "تحية", "سلام", "هاي", "هلو", "hello",
    "hi", "hey", "كيف حالك", "كيف الحال", "شو أخبارك",
]

HELP_WORDS = [
    "مساعدة", "مساعد", "ساعدني", "مساعده",
    "ماذا تستطيع", "ماذا تعرف", "ما قدراتك",
    "ما الذي يمكنك", "ماذا يمكنك", "كيف تعمل",
    "شرح", "اشرح لي", "help", "قائمة الأوامر",
    "ما هي الخيارات", "الخيارات المتاحة",
]

CASE_QUERY_WORDS = [
    "القضايا", "قضايا", "القضية", "قضية",
    "عدد القضايا", "كم قضية", "كم عدد",
    "المفتوحة", "المغلقة", "النشطة", "المنتهية",
    "قضايا هذا الشهر", "قضايا اليوم", "قضايا هذا العام",
    "الحالية", "الجارية", "الجديدة",
]

HEARING_QUERY_WORDS = [
    "الجلسات", "جلسات", "الجلسة", "جلسة",
    "اليوم", "غداً", "غدا", "هذا الأسبوع", "الأسبوع",
    "القادمة", "المقبلة", "المجدولة", "المقررة",
    "موعد", "مواعيد", "جدول", "الجدول",
    "جلسة اليوم", "جلسات غد", "جلسات الأسبوع",
]

CLIENT_QUERY_WORDS = [
    "الموكلين", "موكلين", "الموكل", "موكل",
    "العملاء", "عملاء", "العميل", "عميل",
    "عدد الموكلين", "بيانات موكل", "معلومات موكل",
    "أسم موكل", "اسم الموكل",
]

FINANCE_QUERY_WORDS = [
    "الإيرادات", "إيرادات", "الدخل", "دخل",
    "المصروفات", "مصروفات", "النفقات", "نفقات",
    "الأتعاب", "أتعاب", "الرسوم", "رسوم",
    "المالية", "مالية", "الميزانية", "ميزانية",
    "الأرباح", "أرباح", "الخسائر", "خسائر",
    "كم جمعنا", "كم ربحنا", "إجمالي",
    "المستحقات", "مستحقات", "المدفوعات",
]

TASK_QUERY_WORDS = [
    "المهام", "مهام", "المهمة", "مهمة",
    "المعلقة", "غير المنجزة", "المتأخرة",
    "مهام اليوم", "مهام الأسبوع", "القائمة",
    "التذكيرات", "الأعمال المعلقة",
]

LAW_SEARCH_WORDS = [
    "قانون", "القانون", "المادة", "مادة",
    "الفقرة", "فقرة", "البند", "بند",
    "عقوبة", "العقوبة", "نص", "النص القانوني",
    "ما نص", "ما تقول", "ماذا يقول القانون",
    "قانون العمل", "قانون الأحوال الشخصية",
    "قانون العقوبات", "القانون المدني",
    "قانون التجاري", "قانون الإجراءات",
    "شريعة", "فقه", "حكم شرعي",
    "ابحث في", "ابحث عن",
]

DOCUMENT_GENERATION_WORDS = [
    "أنشئ", "انشئ", "اكتب", "صغ", "أعد",
    "اعمل", "اصنع", "جهز", "هيئ",
    "عقد", "وكالة", "مذكرة", "صحيفة",
    "لائحة", "طعن", "استئناف", "التماس",
    "عريضة", "طلب", "خطاب", "رسالة",
    "تقرير", "محضر", "بروتوكول",
    "توكيل", "وثيقة", "ورقة",
]

STATS_QUERY_WORDS = [
    "إحصائيات", "إحصاء", "نسبة",
    "أداء", "الأداء", "تقرير أداء",
    "نسبة النجاح", "نسبة الفوز", "نسبة الربح",
    "معدل", "المعدل", "متوسط", "المتوسط",
    "مقارنة", "تحليل", "تقييم", "الإنجازات",
]

CASE_SEARCH_WORDS = [
    "ابحث عن قضية", "بحث في القضايا",
    "قضايا عقارية", "قضايا تجارية", "قضايا جزائية",
    "قضايا الأحوال الشخصية", "قضايا مدنية",
    "قضايا المشتري", "قضايا البائع",
    "قضايا العمال", "قضايا الإيجار",
    "جد قضية", "اعثر على",
]

LEGAL_ADVICE_WORDS = [
    "استشارة", "استشارة قانونية", "رأي قانوني",
    "ما حكم", "ما الحكم", "هل يجوز",
    "ما هو الوضع القانوني", "كيف أتصرف",
    "حقي في", "حقوقي", "ما حقوقي",
    "ما التزاماتي", "مسؤوليتي",
    "هل يحق لي", "هل أستطيع",
    "ماذا يترتب", "ما النتائج القانونية",
]

# ─────────────────────────────────────────────
# قوائم أسماء القوانين اليمنية
# ─────────────────────────────────────────────
YEMENI_LAWS = {
    "قانون العمل": ["قانون العمل", "عمال", "العمال", "العمل"],
    "قانون الأحوال الشخصية": ["أحوال شخصية", "الأسرة", "الزواج", "الطلاق", "النفقة", "الحضانة", "الإرث"],
    "قانون العقوبات": ["عقوبات", "العقوبات", "الجرائم", "الجريمة", "السجن"],
    "القانون المدني": ["مدني", "المدني", "العقود", "التعاقد", "الالتزامات"],
    "القانون التجاري": ["تجاري", "التجاري", "الشركات", "التجارة"],
    "قانون الإجراءات الجزائية": ["إجراءات جزائية", "إجراءات", "التحقيق", "الاستجواب"],
    "قانون الإجراءات المدنية": ["إجراءات مدنية", "المرافعات", "الدعوى"],
    "قانون الضرائب": ["ضرائب", "الضريبة", "الضرائب", "الجمارك"],
    "قانون التأمينات الاجتماعية": ["تأمينات", "الضمان الاجتماعي", "المعاشات"],
    "قانون الملكية الفكرية": ["ملكية فكرية", "حقوق النشر", "براءة الاختراع"],
    "قانون الاستثمار": ["استثمار", "الاستثمار", "المستثمرين"],
    "قانون التحكيم": ["تحكيم", "التحكيم", "الوساطة", "الوسيط"],
}

# أنواع الوثائق القانونية
DOCUMENT_TYPES = {
    "عقد": ["عقد", "عقود", "اتفاقية", "اتفاق"],
    "وكالة": ["وكالة", "توكيل", "وكيل"],
    "مذكرة": ["مذكرة", "مذكرة دفاعية", "مذكرة قانونية"],
    "صحيفة دعوى": ["صحيفة", "صحيفة دعوى", "لائحة دعوى"],
    "طعن": ["طعن", "طعن بالاستئناف", "طعن بالنقض"],
    "التماس": ["التماس", "التماس إعادة النظر"],
    "عريضة": ["عريضة", "طلب"],
    "محضر": ["محضر", "بروتوكول", "محضر جلسة"],
    "خطاب": ["خطاب", "رسالة", "مكاتبة"],
    "تقرير خبرة": ["تقرير خبرة", "تقرير فني"],
}


class IntentDetector:
    """
    محرك اكتشاف النية يحلل سؤال المستخدم ويستخرج:
    - نوع النية (intent type)
    - درجة الثقة (confidence)
    - الكيانات المستخرجة (entities: أرقام، تواريخ، أسماء)
    - معلومات إضافية (اسم القانون، رقم المادة، نوع الوثيقة)
    """

    def __init__(self):
        self._build_patterns()

    def _build_patterns(self):
        """بناء أنماط regex للتعرف على الكيانات"""
        self.patterns = {
            # أرقام المواد القانونية
            "article_number": re.compile(
                r"(?:المادة|مادة|الفقرة|فقرة|البند|بند)\s*(?:رقم\s*)?(\d+)",
                re.UNICODE
            ),
            # أرقام عامة
            "numbers": re.compile(r"\b(\d+)\b", re.UNICODE),
            # التواريخ بصيغ مختلفة
            "date_full": re.compile(
                r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})",
                re.UNICODE
            ),
            "date_year": re.compile(r"\b(20\d{2}|19\d{2})\b", re.UNICODE),
            "date_month": re.compile(
                r"(يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|"
                r"أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر|"
                r"محرم|صفر|ربيع|رجب|شعبان|رمضان|شوال|ذو القعدة|ذو الحجة)",
                re.UNICODE
            ),
            # اسم شخص (اسم عربي من كلمتين أو ثلاث)
            "person_name": re.compile(
                r"(?:الموكل|موكل|العميل|المتهم|المدعي|المدعى عليه)\s+([ء-ي\s]{5,35})",
                re.UNICODE
            ),
            # رقم قضية
            "case_number": re.compile(
                r"(?:قضية|رقم|القضية)\s*(?:رقم\s*)?([A-Za-z0-9\-/]+)",
                re.UNICODE
            ),
            # الكلمات المحيطة بـ "من قانون"
            "law_name_after": re.compile(
                r"(?:من|في|قانون)\s+([ء-ي\s]{3,40})",
                re.UNICODE
            ),
            # نسبة مئوية
            "percentage": re.compile(r"(\d+(?:\.\d+)?)\s*%", re.UNICODE),
            # مبالغ مالية
            "amount": re.compile(
                r"(\d[\d,\.]*)\s*(?:ريال|ر\.ي|دولار|\$|USD|YER)",
                re.UNICODE
            ),
        }

    # ──────────────────────────────────────────
    # الدالة الرئيسية
    # ──────────────────────────────────────────
    def detect(self, question: str) -> Intent:
        """
        يحلل سؤال المستخدم ويعيد كائن Intent يحمل كل التفاصيل.

        Args:
            question: نص السؤال أو الأمر من المستخدم

        Returns:
            Intent: كائن يحمل نوع النية ودرجة الثقة والكيانات
        """
        if not question or not question.strip():
            return Intent(type="unknown", confidence=0.0, entities={})

        normalized = self._normalize(question)
        entities = self._extract_entities(normalized, question)

        # ترتيب محاولات الكشف من الأكثر تخصصاً للأقل
        detectors: List[Tuple[str, float, dict]] = []

        detectors.append(self._detect_greeting(normalized))
        detectors.append(self._detect_help(normalized))
        detectors.append(self._detect_law_search(normalized, entities))
        detectors.append(self._detect_document_generation(normalized, entities))
        detectors.append(self._detect_hearing_query(normalized, entities))
        detectors.append(self._detect_case_search(normalized, entities))
        detectors.append(self._detect_case_query(normalized, entities))
        detectors.append(self._detect_client_query(normalized, entities))
        detectors.append(self._detect_finance_query(normalized))
        detectors.append(self._detect_task_query(normalized))
        detectors.append(self._detect_stats_query(normalized))
        detectors.append(self._detect_legal_advice(normalized))

        # اختر النية بأعلى ثقة
        best = max(detectors, key=lambda x: x[1])
        intent_type, confidence, extra = best

        return Intent(
            type=intent_type,
            confidence=round(confidence, 2),
            entities=entities,
            sub_type=extra.get("sub_type"),
            law_name=extra.get("law_name"),
            article_number=extra.get("article_number"),
            document_type=extra.get("document_type"),
        )

    # ──────────────────────────────────────────
    # كاشفات النية الفردية
    # ──────────────────────────────────────────

    def _detect_greeting(self, text: str) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, GREETING_WORDS, boost_exact=True)
        return ("greeting", min(score * 1.5, 1.0), {})

    def _detect_help(self, text: str) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, HELP_WORDS, boost_exact=True)
        return ("help", min(score * 1.5, 1.0), {})

    def _detect_law_search(self, text: str, entities: dict) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, LAW_SEARCH_WORDS)
        extra: Dict = {}

        # استخراج رقم المادة
        art_match = self.patterns["article_number"].search(text)
        if art_match:
            extra["article_number"] = art_match.group(1)
            score = min(score + 0.3, 1.0)

        # استخراج اسم القانون
        for law_key, keywords in YEMENI_LAWS.items():
            if any(kw in text for kw in keywords):
                extra["law_name"] = law_key
                score = min(score + 0.2, 1.0)
                break

        if extra.get("article_number") and not score:
            score = 0.6

        return ("search_law", score, extra)

    def _detect_document_generation(self, text: str, entities: dict) -> Tuple[str, float, dict]:
        action_score = self._keyword_score(text, DOCUMENT_GENERATION_WORDS[:10])  # أفعال الإنشاء
        doc_score = 0.0
        extra: Dict = {}

        for doc_type, keywords in DOCUMENT_TYPES.items():
            if any(kw in text for kw in keywords):
                extra["document_type"] = doc_type
                doc_score = 0.5
                break

        score = min(action_score * 0.7 + doc_score, 1.0)
        return ("generate_document", score, extra)

    def _detect_hearing_query(self, text: str, entities: dict) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, HEARING_QUERY_WORDS)
        extra: Dict = {}

        if "اليوم" in text:
            extra["sub_type"] = "today"
            score = min(score + 0.2, 1.0)
        elif "غداً" in text or "غدا" in text:
            extra["sub_type"] = "tomorrow"
            score = min(score + 0.2, 1.0)
        elif "الأسبوع" in text or "هذا الأسبوع" in text:
            extra["sub_type"] = "this_week"
            score = min(score + 0.15, 1.0)
        elif "الشهر" in text:
            extra["sub_type"] = "this_month"

        return ("query_hearings", score, extra)

    def _detect_case_query(self, text: str, entities: dict) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, CASE_QUERY_WORDS)
        extra: Dict = {}

        if "مفتوح" in text or "نشط" in text or "جار" in text:
            extra["sub_type"] = "open"
        elif "مغلق" in text or "منتهي" in text or "مكتمل" in text:
            extra["sub_type"] = "closed"
        elif "هذا الشهر" in text or "الشهر الحالي" in text:
            extra["sub_type"] = "this_month"
        elif "هذا العام" in text or "العام الحالي" in text:
            extra["sub_type"] = "this_year"
        elif "اليوم" in text:
            extra["sub_type"] = "today"

        return ("query_cases", score, extra)

    def _detect_client_query(self, text: str, entities: dict) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, CLIENT_QUERY_WORDS)
        extra: Dict = {}

        name_match = self.patterns["person_name"].search(text)
        if name_match:
            extra["client_name"] = name_match.group(1).strip()
            extra["sub_type"] = "specific_client"
            score = min(score + 0.3, 1.0)

        return ("query_clients", score, extra)

    def _detect_finance_query(self, text: str) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, FINANCE_QUERY_WORDS)
        extra: Dict = {}

        if "إيراد" in text or "دخل" in text:
            extra["sub_type"] = "income"
        elif "مصروف" in text or "نفقة" in text or "خسارة" in text:
            extra["sub_type"] = "expense"
        elif "أتعاب" in text or "رسوم" in text:
            extra["sub_type"] = "fees"
        elif "ميزانية" in text or "إجمالي" in text:
            extra["sub_type"] = "summary"

        return ("query_finance", score, extra)

    def _detect_task_query(self, text: str) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, TASK_QUERY_WORDS)
        extra: Dict = {}

        if "معلق" in text or "غير منجز" in text or "متأخر" in text:
            extra["sub_type"] = "pending"
        elif "اليوم" in text:
            extra["sub_type"] = "today"
        elif "الأسبوع" in text:
            extra["sub_type"] = "this_week"

        return ("query_tasks", score, extra)

    def _detect_stats_query(self, text: str) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, STATS_QUERY_WORDS)
        extra: Dict = {}

        if "نجاح" in text or "فوز" in text:
            extra["sub_type"] = "success_rate"
        elif "أداء" in text:
            extra["sub_type"] = "performance"
        elif "مقارنة" in text:
            extra["sub_type"] = "comparison"

        return ("analyze_stats", score, extra)

    def _detect_case_search(self, text: str, entities: dict) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, CASE_SEARCH_WORDS)
        extra: Dict = {}

        case_match = self.patterns["case_number"].search(text)
        if case_match:
            extra["case_number"] = case_match.group(1)
            score = min(score + 0.4, 1.0)

        # كلمة مفتاحية بحثية
        if "ابحث" in text and "قضي" in text:
            score = min(score + 0.3, 1.0)

        # نوع القضية
        for case_type in ["عقاري", "تجاري", "جزائي", "مدني", "أسرة", "عمال", "إيجار"]:
            if case_type in text:
                extra["case_type"] = case_type
                score = min(score + 0.15, 1.0)
                break

        return ("search_case", score, extra)

    def _detect_legal_advice(self, text: str) -> Tuple[str, float, dict]:
        score = self._keyword_score(text, LEGAL_ADVICE_WORDS)
        return ("legal_advice", score, {})

    # ──────────────────────────────────────────
    # استخراج الكيانات
    # ──────────────────────────────────────────

    def _extract_entities(self, normalized: str, original: str) -> Dict:
        """يستخرج جميع الكيانات من النص"""
        entities: Dict = {}

        # الأرقام
        numbers = self.patterns["numbers"].findall(normalized)
        if numbers:
            entities["numbers"] = [int(n) for n in numbers]

        # التواريخ الكاملة
        date_matches = self.patterns["date_full"].findall(original)
        if date_matches:
            entities["dates"] = [
                {"day": m[0], "month": m[1], "year": m[2]}
                for m in date_matches
            ]

        # السنة
        year_matches = self.patterns["date_year"].findall(original)
        if year_matches:
            entities["years"] = [int(y) for y in year_matches]

        # الشهر
        month_match = self.patterns["date_month"].search(original)
        if month_match:
            entities["month_name"] = month_match.group(1)

        # رقم المادة
        art_match = self.patterns["article_number"].search(original)
        if art_match:
            entities["article_number"] = art_match.group(1)

        # المبالغ
        amount_matches = self.patterns["amount"].findall(original)
        if amount_matches:
            entities["amounts"] = amount_matches

        # النسب المئوية
        pct_matches = self.patterns["percentage"].findall(original)
        if pct_matches:
            entities["percentages"] = [float(p) for p in pct_matches]

        # رقم القضية
        case_match = self.patterns["case_number"].search(original)
        if case_match:
            entities["case_number"] = case_match.group(1)

        # كلمات دالة على الزمن
        entities["time_context"] = self._extract_time_context(normalized)

        return entities

    def _extract_time_context(self, text: str) -> Optional[str]:
        """يحدد السياق الزمني من النص"""
        if "اليوم" in text:
            return "today"
        if "غداً" in text or "غدا" in text or "بكرة" in text:
            return "tomorrow"
        if "أمس" in text:
            return "yesterday"
        if "هذا الأسبوع" in text or "الأسبوع الحالي" in text:
            return "this_week"
        if "الأسبوع القادم" in text or "الأسبوع المقبل" in text:
            return "next_week"
        if "هذا الشهر" in text or "الشهر الحالي" in text:
            return "this_month"
        if "الشهر الماضي" in text:
            return "last_month"
        if "هذا العام" in text or "هذه السنة" in text:
            return "this_year"
        if "العام الماضي" in text or "السنة الماضية" in text:
            return "last_year"
        return None

    # ──────────────────────────────────────────
    # دوال مساعدة
    # ──────────────────────────────────────────

    def _normalize(self, text: str) -> str:
        """تطبيع النص العربي"""
        text = text.strip().lower()
        # توحيد الهمزات
        text = re.sub(r"[أإآ]", "ا", text)
        text = re.sub(r"ى", "ي", text)
        text = re.sub(r"ة", "ه", text)
        # إزالة التشكيل
        text = re.sub(r"[\u064B-\u065F]", "", text)
        # إزالة الرموز غير المفيدة
        text = re.sub(r"[؟?!،,\.\-]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _keyword_score(
        self,
        text: str,
        keywords: List[str],
        boost_exact: bool = False
    ) -> float:
        """
        يحسب درجة التطابق مع قائمة كلمات مفتاحية.
        يعيد قيمة بين 0.0 و 1.0
        """
        if not text or not keywords:
            return 0.0

        hits = sum(1 for kw in keywords if kw in text)
        if hits == 0:
            return 0.0

        base_score = min(hits / max(len(keywords) * 0.3, 1), 1.0)

        if boost_exact and any(kw == text.strip() for kw in keywords):
            base_score = min(base_score + 0.4, 1.0)

        return round(base_score, 3)

    def batch_detect(self, questions: List[str]) -> List[Intent]:
        """يعالج قائمة من الأسئلة دفعةً واحدة"""
        return [self.detect(q) for q in questions]

    def get_intent_label(self, intent_type: str) -> str:
        """يعيد التسمية العربية لنوع النية"""
        return INTENT_TYPES.get(intent_type, "غير معروف")
