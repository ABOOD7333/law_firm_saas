"""
Contract Analyzer Service — AI-Powered (Gemini)
محرك تحليل العقود الذكي باستخدام Gemini API

المميزات:
- استخراج الكيانات القانونية المعقدة (أطراف، التزامات، شروط جزائية، تواريخ، مبالغ)
- كشف المخاطر القانونية ومقارنتها بالقانون المدني اليمني
- مقارنة نسختين من العقد وإظهار الفروق (Document Diff)
"""
import os
import re
import json
import difflib
from typing import Dict, Any, List, Optional


def _get_gemini_client():
    """الحصول على عميل Gemini (Lazy Loading)"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.environ.get("GEMINI_API_KEY", "").strip()
            except Exception:
                pass
        if not api_key:
            return None, "GEMINI_API_KEY غير موجود"
        from google import genai
        client = genai.Client(api_key=api_key)
        return client, None
    except Exception as e:
        return None, str(e)


# ─── بنود القانون المدني اليمني عالية المخاطر ────────────────────────────────
RISKY_CLAUSES_REFERENCE = [
    {
        "pattern": r"إسقاط.*حق.*النفقة|النفقة.*مسقطة",
        "risk": "عالي",
        "law": "القانون المدني م.166",
        "description": "بند إسقاط حق النفقة يخالف نص القانون المدني اليمني — النفقة حق لا يسقط بالاتفاق"
    },
    {
        "pattern": r"تنازل.*حق.*التقاضي|إسقاط.*حق.*المطالبة",
        "risk": "عالي",
        "law": "قانون المرافعات م.1",
        "description": "الاتفاق على إسقاط حق التقاضي باطل وفق القانون اليمني"
    },
    {
        "pattern": r"غرامة.*تأخير|جزاء.*تأخير",
        "risk": "متوسط",
        "law": "القانون المدني م.150",
        "description": "شرط الغرامة — تأكد أن النسبة لا تجاوز الضرر الفعلي"
    },
    {
        "pattern": r"فسخ.*دون.*إشعار|إنهاء.*فوري.*دون",
        "risk": "متوسط",
        "law": "القانون المدني م.200",
        "description": "الإنهاء الفوري بدون إشعار قد يُعدّ إخلالاً بالعقد"
    },
    {
        "pattern": r"ربا|فائدة.*مركبة|فوائد.*متراكمة",
        "risk": "عالي",
        "law": "القانون التجاري م.1",
        "description": "شرط الربا أو الفوائد المركبة مخالف للشريعة الإسلامية والقانون اليمني"
    },
    {
        "pattern": r"تنازل.*ملكية.*دون.*مقابل|تمليك.*مجاناً",
        "risk": "منخفض",
        "law": "القانون المدني م.91",
        "description": "بند تنازل عن الملكية دون مقابل — راجع صياغته لتجنب النزاع"
    },
    {
        "pattern": r"تحكيم.*خارج.*اليمن|قانون.*أجنبي",
        "risk": "متوسط",
        "law": "قانون التحكيم اليمني م.1",
        "description": "اختيار قانون أجنبي أو تحكيم خارجي قد لا يكون نافذاً في اليمن"
    },
]


class ContractAnalyzerAI:

    def __init__(self):
        # Regex fallback patterns
        self.money_pattern = r'(\d{1,3}(?:,\d{3})*(?:\.\d{2,3})?\s*(?:ريال|دولار|يورو|جنيه|USD|YER|SAR))'
        self.date_pattern = r'(\d{1,2}\s*[/\-]\s*\d{1,2}\s*[/\-]\s*\d{2,4})'
        self.party_pattern = (
            r'(?:الطرف الأول|الطرف الثاني|الطرف الثالث|السيد[/:]|السادة[/:]'
            r'|المقاول[/:]|المؤجر[/:]|المستأجر[/:]|البائع[/:]|المشتري[/:]|الموكل[/:]|الوكيل[/:])'
            r'\s*[:\-]?\s*([\u0600-\u06FF\w\s]{3,40}?)(?:الذي|ويحمل|بطاقة|الجنسية|والمقيم|\n|$)'
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. التحليل الكامل بـ Gemini
    # ─────────────────────────────────────────────────────────────────────────
    def analyze_contract_ai(self, text: str) -> Dict[str, Any]:
        """تحليل كامل للعقد باستخدام Gemini API"""

        client, error = _get_gemini_client()

        if not client:
            return self._analyze_contract_regex(text, gemini_error=error)

        prompt = f"""أنت محامٍ يمني خبير ومتخصص في تحليل العقود القانونية.
قم بتحليل العقد التالي وأعد النتيجة بصيغة JSON فقط (بدون أي نص إضافي قبل أو بعد):

{{
  "contract_type": "نوع العقد (عقد إيجار / عقد بيع / عقد خدمات / عقد توريد / عقد عمل / غير محدد)",
  "parties": [
    {{"name": "اسم الطرف", "role": "دوره في العقد (مؤجر/مستأجر/بائع/مشتري/إلخ)", "id_info": "رقم الهوية أو السجل التجاري إذا ذُكر"}}
  ],
  "obligations": [
    {{"party": "اسم الطرف", "obligation": "وصف الالتزام بدقة"}}
  ],
  "penalty_clauses": [
    {{"condition": "شرط تفعيل الغرامة", "amount": "المبلغ أو النسبة", "party_liable": "الطرف المسؤول"}}
  ],
  "key_dates": [
    {{"label": "وصف التاريخ", "date": "التاريخ"}}
  ],
  "financial_terms": [
    {{"label": "وصف المبلغ", "amount": "المبلغ والعملة", "payment_schedule": "جدول الدفع إن وجد"}}
  ],
  "summary": "ملخص موجز للعقد في 3 جمل"
}}

نص العقد:
---
{text[:8000]}
---"""

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            raw = response.text.strip()
            # تنظيف أي markdown
            raw = re.sub(r'^```json\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            result = json.loads(raw)
            result["is_ai_used"] = True
            result["ai_model"] = "gemini-2.0-flash"
            return result
        except json.JSONDecodeError:
            # إذا لم يُرجع JSON نظيف، نرجع ما تيسر
            return {
                "is_ai_used": True,
                "ai_model": "gemini-2.0-flash",
                "raw_analysis": response.text,
                "summary": response.text[:500],
                "parties": [], "obligations": [], "penalty_clauses": [],
                "key_dates": [], "financial_terms": [], "contract_type": "غير محدد"
            }
        except Exception as e:
            return self._analyze_contract_regex(text, gemini_error=str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # 2. كشف المخاطر القانونية
    # ─────────────────────────────────────────────────────────────────────────
    def detect_risks(self, text: str) -> Dict[str, Any]:
        """يكشف البنود عالية المخاطر ويقارنها بالقانون المدني اليمني"""

        client, error = _get_gemini_client()

        # فحص Regex أولاً
        regex_risks = []
        for ref in RISKY_CLAUSES_REFERENCE:
            if re.search(ref["pattern"], text, re.IGNORECASE):
                regex_risks.append({
                    "risk_level": ref["risk"],
                    "law_reference": ref["law"],
                    "description": ref["description"],
                    "detected_by": "regex"
                })

        if not client:
            return {
                "is_ai_used": False,
                "risks": regex_risks,
                "overall_risk": self._calculate_overall_risk(regex_risks),
                "recommendation": "يُنصح بمراجعة العقد مع محامٍ متخصص" if regex_risks else "لم يتم اكتشاف مخاطر واضحة بالفحص الأولي"
            }

        prompt = f"""أنت محامٍ يمني متخصص في تدقيق العقود. حلل العقد التالي وأعد قائمة بجميع البنود عالية المخاطر أو المخالفة للقانون اليمني.
أعد النتيجة بصيغة JSON فقط:

{{
  "risks": [
    {{
      "clause_text": "نص البند المشكوك فيه (أول 100 حرف)",
      "risk_level": "عالي | متوسط | منخفض",
      "law_reference": "المادة القانونية المخالفة",
      "description": "وصف المخاطرة القانونية",
      "recommendation": "التوصية للمعالجة"
    }}
  ],
  "overall_risk": "عالي | متوسط | منخفض | آمن",
  "recommendation": "التوصية العامة للمحامي"
}}

نص العقد:
---
{text[:6000]}
---"""

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            raw = response.text.strip()
            raw = re.sub(r'^```json\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            result = json.loads(raw)
            result["is_ai_used"] = True
            # دمج نتائج Regex مع Gemini
            result["risks"] = result.get("risks", []) + [r for r in regex_risks if r not in result.get("risks", [])]
            return result
        except Exception as e:
            return {
                "is_ai_used": False,
                "risks": regex_risks,
                "overall_risk": self._calculate_overall_risk(regex_risks),
                "recommendation": f"تعذر التحليل الذكي: {str(e)}"
            }

    # ─────────────────────────────────────────────────────────────────────────
    # 3. مقارنة نسختي العقد (Document Diff)
    # ─────────────────────────────────────────────────────────────────────────
    def compare_contracts(self, text1: str, text2: str, label1: str = "النسخة الأولى", label2: str = "النسخة الثانية") -> Dict[str, Any]:
        """مقارنة نسختين من العقد وإظهار الفروق"""

        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            lines1, lines2,
            fromfile=label1,
            tofile=label2,
            lineterm=""
        ))

        # إحصائيات
        added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
        changed_sections = sum(1 for l in diff if l.startswith('@@'))

        # diff مُنسَّق للعرض
        diff_html_lines = []
        for line in diff:
            if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
                diff_html_lines.append({"type": "header", "text": line})
            elif line.startswith('+'):
                diff_html_lines.append({"type": "added", "text": line[1:]})
            elif line.startswith('-'):
                diff_html_lines.append({"type": "removed", "text": line[1:]})
            else:
                diff_html_lines.append({"type": "unchanged", "text": line})

        # تحليل Gemini للفروق الجوهرية
        client, _ = _get_gemini_client()
        ai_summary = None

        if client and (added > 0 or removed > 0):
            diff_text = "".join(diff[:100])  # أول 100 سطر من الـ diff
            prompt = f"""قارن بين نسختين من عقد قانوني يمني. الفروق هي:
---
{diff_text}
---
أعد تحليلاً موجزاً بالعربية للفروق الجوهرية بين النسختين وأثرها القانوني في 5 نقاط أو أقل."""
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                ai_summary = response.text.strip()
            except Exception:
                pass

        return {
            "label1": label1,
            "label2": label2,
            "stats": {
                "added_lines": added,
                "removed_lines": removed,
                "changed_sections": changed_sections,
                "similarity_ratio": round(difflib.SequenceMatcher(None, text1, text2).ratio() * 100, 1)
            },
            "diff": diff_html_lines,
            "ai_summary": ai_summary,
            "is_ai_used": ai_summary is not None
        }

    # ─────────────────────────────────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────────────────────────────────
    def _analyze_contract_regex(self, text: str, gemini_error: str = None) -> Dict[str, Any]:
        """تحليل Regex كـ fallback عند عدم توفر Gemini"""
        moneys = list(set(re.findall(self.money_pattern, text)))
        dates = list(set(re.findall(self.date_pattern, text)))
        parties_raw = re.findall(self.party_pattern, text)
        parties = [{"name": p.strip(), "role": "طرف في العقد", "id_info": ""} for p in parties_raw if len(p.strip()) > 3]

        return {
            "is_ai_used": False,
            "gemini_error": gemini_error,
            "contract_type": "غير محدد",
            "parties": parties,
            "obligations": [],
            "penalty_clauses": [],
            "key_dates": [{"label": "تاريخ", "date": d} for d in dates],
            "financial_terms": [{"label": "مبلغ", "amount": m, "payment_schedule": ""} for m in moneys],
            "summary": "تم التحليل بالطريقة الأساسية (Regex). يُنصح برفع العقد مع اتصال إنترنت للحصول على التحليل الكامل."
        }

    def _calculate_overall_risk(self, risks: List[Dict]) -> str:
        if not risks:
            return "آمن"
        levels = [r.get("risk_level", "") for r in risks]
        if "عالي" in levels:
            return "عالي"
        if "متوسط" in levels:
            return "متوسط"
        return "منخفض"


# Singleton
analyzer_service = ContractAnalyzerAI()
