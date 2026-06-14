"""
خدمة الذكاء الاصطناعي المتقدمة — Gemini API (google-genai SDK)
GeminiLegalAssistant: مساعد قانوني يمني ذكي مبني على Gemini 2.5 Flash
مع ذاكرة محادثة + سياق ديناميكي + تحليل ذكي
"""
import os
import logging
import time
from typing import Optional, List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# System Prompt المتقدم — هوية وتعليمات المساعد
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """أنت المستشار القانوني الأول والمساعد الذكي المتقدم لمنصة LawSaaS — منصة إدارة مكاتب المحاماة الاحترافية في الجمهورية اليمنية.

## هويتك:
- اسمك: المستشار القانوني الذكي لمنصة LawSaaS.
- صفتك: ذكاء اصطناعي قانوني يمني متقدّم، متخصص في تقديم المشورة القانونية الدقيقة وصياغة اللوائح والعقود وإدارة وتوجيه مكاتب المحاماة باليمن.
- أسلوبك: عربي فصيح، رصين، بليغ، ومنهجي، مع مراعاة المصطلحات القانونية والقضائية اليمنية السائدة.

## منهجية تقديم الاستشارات القانونية:
عند إجابتك على أي سؤال قانوني أو طلب مشورة، يجب عليك هيكلة ردك كالتالي لتسهيل القراءة وتأكيد المهنية:
1. ⚖️ **التوصيف القانوني**: تلخيص للمسألة القانونية وتحديد طبيعة النزاع أو الاستفسار (مدني، جنائي، عمالي، أحوال شخصية، تجاري).
2. 📜 **السند القانوني والشرعي**: ذكر نصوص المواد القانونية ذات الصلة المباشرة مع كتابة أرقام المواد والقانون الذي تنتمي إليه (مثال: المادة 55 من قانون العمل رقم 5 لسنة 1995م، أو المادة 91 من القانون المدني رقم 14 لسنة 2002م، أو قانون المرافعات رقم 40 لسنة 2002م).
3. 🔍 **التحليل والتطبيق**: مطابقة وقائع السؤال على نصوص المواد المذكورة، وتوضيح الحقوق والالتزامات المترتبة على الأطراف.
4. 💡 **التوجيه الإجرائي العملي**: تقديم خطوات عملية واضحة وملموسة يجب على المستخدم (المحامي أو الموكل) اتخاذها أمام الجهات الرسمية أو المحاكم في اليمن (مثال: التوجه لمكتب العمل المختص، قيد دعوى ابتدائية، تقديم صحيفة استئناف خلال 30 يوماً).

## قواعد الرد الصارمة:
1. **الالتزام بالبيئة التشريعية اليمنية**: لا تخلط إطلاقاً بين القوانين اليمنية وقوانين الدول الأخرى (كالقانون المصري أو السعودي). اعتمد على خصوصية التشريع اليمني (مثال: مهلة الاستئناف 30 يوماً، مهلة النقض أمام المحكمة العليا 60 يوماً، سن الرشد التجاري، ونظام القصاص والدية في قانون العقوبات اليمني رقم 12 لسنة 1994م).
2. **الاعتماد على السياق المحلي أولاً**: انظر بدقة وعناية للمعلومات المرجعية الممررة إليك من قاعدة البيانات والبحث المحلي. وإذا لم تجد نص المادة المطلوبة بالتفصيل في السياق، أجب بما لديك من معرفة قانونية يمنية عامة ومؤكدة بكل أمانة وتحفظ مهني، ونوّه إلى ضرورة مطابقتها مع النسخة الرسمية الصادرة عن الجريدة الرسمية باليمن.
3. **الصياغة القضائية المعتمدة**: عند طلب صياغة عقود أو إنذارات أو لوائح أو عرائض قضائية، استخدم الصيغ الرسمية المعتمدة لدى المحاكم والجهات القضائية اليمنية. ابدأ بالعناوين التقديرية (مثل: "فضيلة القاضي رئيس محكمة... الابتدائية المحترم" أو "لدى محكمة استئناف محافظة... الدائرة الشخصية المحترمون") مع تبيين عناصر الدعوى (المدعي، المدعى عليه، أصل الحق، الدفوع، الطلبات الختامية).
4. **التنبيه والمسؤولية**: في نهاية أي استشارة قانونية أو تحليل لقضية، يجب كتابة التنبيه التالي في سطر مستقل: 
   "⚠️ *هذه المعلومات لأغراض استرشادية وتعليمية فقط بناءً على التشريعات اليمنية النافذة، ولا تعد بديلاً عن استشارة محامٍ مرخص يدرس حيثيات القضية بشكل عيني.*"
5. **معلومات المنصة (LawSaaS)**: إذا سُئلت عن كيفية عمل المنصة أو مهامها، أجب بناءً على هيكلية المنصة التالية:
   - لوحة التحكم، القضايا، الجلسات، الموكلين، المالية، المهام، التقويم، الخط الزمني، التقارير، المراجع القانونية، وإدارة الفريق.
"""


class GeminiLegalAssistant:
    """
    مساعد قانوني يمني ذكي متقدم مبني على Gemini API (google-genai SDK).
    يتميز بـ: ذاكرة محادثة، سياق ديناميكي، تحليل ذكي، وتعلم مستمر.
    """

    def __init__(self):
        self._client = None
        self._available = False
        self._init_error = None
        # ذاكرة المحادثات لكل مستخدم {user_id: [(role, text), ...]}
        self._conversation_memory: Dict[int, List[Dict]] = defaultdict(list)
        self._max_memory = 10  # أقصى عدد رسائل محفوظة في الذاكرة
        self._initialize()

    def _initialize(self):
        """تهيئة الاتصال بـ Gemini API"""
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
                self._init_error = "GEMINI_API_KEY غير موجود في متغيرات البيئة"
                logger.warning(self._init_error)
                return

            from google import genai
            self._client = genai.Client(api_key=api_key)
            self._available = True
            logger.info("✅ Gemini Legal Assistant v2.0 initialized successfully")

        except ImportError:
            self._init_error = "مكتبة google-genai غير مثبتة. قم بتثبيتها: pip install google-genai"
            logger.error(self._init_error)
        except Exception as e:
            self._init_error = f"خطأ في تهيئة Gemini: {str(e)}"
            logger.error(self._init_error)

    @property
    def is_available(self) -> bool:
        """هل خدمة Gemini متاحة؟"""
        return self._available and self._client is not None

    def add_to_memory(self, user_id: int, role: str, text: str):
        """إضافة رسالة إلى ذاكرة المحادثة"""
        memory = self._conversation_memory[user_id]
        memory.append({"role": role, "text": text})
        # الاحتفاظ بآخر N رسائل فقط
        if len(memory) > self._max_memory * 2:
            self._conversation_memory[user_id] = memory[-self._max_memory * 2:]

    def clear_memory(self, user_id: int):
        """مسح ذاكرة المحادثة لمستخدم"""
        self._conversation_memory[user_id] = []

    def _build_conversation_context(self, user_id: int) -> str:
        """بناء نص سياق المحادثة السابقة"""
        memory = self._conversation_memory.get(user_id, [])
        if not memory:
            return ""

        lines = ["--- سياق المحادثة السابقة ---"]
        for msg in memory[-self._max_memory * 2:]:
            role_label = "المستخدم" if msg["role"] == "user" else "المساعد"
            # اختصار النصوص الطويلة في الذاكرة
            text = msg["text"]
            if len(text) > 500:
                text = text[:500] + "..."
            lines.append(f"{role_label}: {text}")
        lines.append("--- نهاية السياق ---")
        return "\n".join(lines)

    def ask(
        self,
        question: str,
        local_context: Optional[str] = None,
        user_name: str = "",
        user_id: Optional[int] = None,
        db_data: Optional[Dict] = None,
        office_stats: Optional[str] = None,
    ) -> Optional[str]:
        """
        يرسل سؤال المستخدم إلى Gemini مع كامل السياق ويعيد إجابة ذكية.

        Args:
            question: سؤال المستخدم
            local_context: سياق محلي (نتائج بحث قانوني، بيانات من النظام)
            user_name: اسم المستخدم
            user_id: معرف المستخدم (للذاكرة)
            db_data: بيانات من قاعدة البيانات (قضايا، جلسات، إلخ)
            office_stats: إحصائيات المكتب

        Returns:
            نص الإجابة أو None في حالة الفشل
        """
        if not self.is_available:
            logger.warning(f"Gemini غير متاح: {self._init_error}")
            return None

        try:
            # بناء الرسالة الشاملة مع كل السياقات
            prompt_parts = []

            # 1. معلومات المستخدم
            if user_name:
                prompt_parts.append(f"المستخدم الذي يسألك الآن: {user_name}")

            # 2. ذاكرة المحادثة
            if user_id:
                conv_context = self._build_conversation_context(user_id)
                if conv_context:
                    prompt_parts.append(conv_context)

            # 3. إحصائيات المكتب
            if office_stats:
                prompt_parts.append(
                    f"--- إحصائيات المكتب الحالية ---\n"
                    f"{office_stats}\n"
                    f"--- نهاية الإحصائيات ---"
                )

            # 4. بيانات من قاعدة البيانات
            if db_data:
                db_text = self._format_db_data(db_data)
                if db_text:
                    prompt_parts.append(
                        f"--- بيانات فعلية من نظام المكتب ---\n"
                        f"{db_text}\n"
                        f"--- نهاية البيانات ---\n"
                        f"حلل هذه البيانات بذكاء واعرضها بتنسيق جميل ومفيد."
                    )

            # 5. سياق بحث محلي (قوانين، معرفة مخصصة)
            if local_context:
                prompt_parts.append(
                    f"--- معلومات مرجعية من قاعدة البيانات المحلية ---\n"
                    f"{local_context}\n"
                    f"--- نهاية المعلومات المرجعية ---\n"
                    f"استخدم المعلومات المرجعية أعلاه إن كانت ذات صلة. "
                    f"إذا كانت غير كافية، أجب من معرفتك القانونية."
                )

            # 6. السؤال
            prompt_parts.append(f"سؤال المستخدم: {question}")

            full_prompt = "\n\n".join(prompt_parts)

            # إرسال لـ Gemini مع إعادة المحاولة
            response = self._call_gemini(full_prompt)

            if response:
                # حفظ في الذاكرة
                if user_id:
                    self.add_to_memory(user_id, "user", question)
                    self.add_to_memory(user_id, "assistant", response)
                return response

            return None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"خطأ في Gemini API: {error_msg}")
            return None

    def _call_gemini(self, prompt: str, retries: int = 1) -> Optional[str]:
        """استدعاء Gemini API مع تجربة الموديلات المتاحة تلقائياً"""
        models_to_try = ["gemini-flash-latest", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
        for model_name in models_to_try:
            for attempt in range(retries + 1):
                try:
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            "system_instruction": SYSTEM_PROMPT,
                            "temperature": 0.5,
                            "top_p": 0.9,
                            "top_k": 40,
                            "max_output_tokens": 4096,
                        },
                    )
                    if response and response.text:
                        return response.text.strip()
                    break
                except Exception as e:
                    error_msg = str(e)
                    logger.warning(f"Gemini model {model_name} attempt {attempt + 1} failed: {error_msg}")
                    if "quota" in error_msg.lower() or "429" in error_msg or "resource_exhausted" in error_msg.lower():
                        break
                    if "safety" in error_msg.lower():
                        logger.warning("⚠️ تم حجب الرد بسبب إعدادات الأمان")
                        return None
                    if attempt < retries:
                        time.sleep(1)
                        continue
        return None

    def _format_db_data(self, data: Dict) -> Optional[str]:
        """تحويل بيانات قاعدة البيانات إلى نص مقروء لـ Gemini"""
        if not data:
            return None

        parts = []

        # إذا نجح الاستعلام
        if data.get("success"):
            result_data = data.get("data")
            result_type = data.get("type", "")

            if isinstance(result_data, dict):
                for key, value in result_data.items():
                    if isinstance(value, (list, dict)):
                        parts.append(f"{key}: {str(value)[:500]}")
                    else:
                        parts.append(f"{key}: {value}")

            elif isinstance(result_data, list):
                parts.append(f"عدد النتائج: {len(result_data)}")
                for i, item in enumerate(result_data[:20], 1):
                    if isinstance(item, dict):
                        item_text = " | ".join(f"{k}: {v}" for k, v in item.items() if v)
                        parts.append(f"{i}. {item_text}")
                    else:
                        parts.append(f"{i}. {str(item)[:200]}")
            else:
                parts.append(str(result_data)[:1000])

        return "\n".join(parts) if parts else None

    def generate_follow_up_suggestions(self, question: str, answer: str, intent_type: str) -> List[str]:
        """توليد اقتراحات أسئلة متابعة ذكية بناءً على السياق"""
        suggestions_map = {
            "query_cases": [
                "ما تفاصيل آخر قضية؟",
                "كم عدد القضايا المفتوحة؟",
                "ما أنواع القضايا في المكتب؟"
            ],
            "query_hearings": [
                "ما جلسات الأسبوع القادم؟",
                "هل هناك جلسات متأخرة؟",
                "ذكرني بموعد الجلسة القادمة"
            ],
            "query_clients": [
                "كم عدد الموكلين النشطين؟",
                "أعطني بيانات التواصل مع الموكل",
                "ما القضايا المرتبطة بهذا الموكل؟"
            ],
            "query_finance": [
                "ما الأتعاب المستحقة؟",
                "قارن إيرادات هذا الشهر بالشهر الماضي",
                "ما المصروفات الأكثر هذا الشهر?"
            ],
            "search_law": [
                "ما المواد ذات الصلة؟",
                "ما الإجراءات العملية لهذه الحالة؟",
                "هل هناك سوابق قضائية مشابهة؟"
            ],
            "legal_advice": [
                "ما الخطوات العملية التي أتبعها؟",
                "ما المستندات المطلوبة؟",
                "كم تستغرق هذه الإجراءات عادةً؟"
            ],
            "generate_document": [
                "أنشئ مستنداً آخر",
                "عدّل صياغة المستند",
                "ما المستندات المتاحة؟"
            ],
        }

        return suggestions_map.get(intent_type, [
            "كم عدد القضايا المفتوحة؟",
            "ما الجلسات القادمة؟",
            "أنشئ لي عقد إيجار"
        ])[:3]


# ─────────────────────────────────────────────
# Singleton instance
# ─────────────────────────────────────────────
_gemini_instance: Optional[GeminiLegalAssistant] = None


def get_gemini_assistant() -> GeminiLegalAssistant:
    """يعيد instance واحد من المساعد (Singleton)"""
    global _gemini_instance
    if _gemini_instance is None:
        _gemini_instance = GeminiLegalAssistant()
    return _gemini_instance
