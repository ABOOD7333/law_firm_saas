"""
خدمة الذكاء الاصطناعي - Gemini API (New SDK: google-genai)
GeminiLegalAssistant: مساعد قانوني يمني ذكي مبني على Gemini
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# System Prompt - الهوية والتعليمات
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """أنت المساعد القانوني الذكي لمنصة LawSaaS — منصة إدارة مكاتب المحاماة في اليمن.

## هويتك:
- اسمك: المساعد القانوني الذكي لمنصة LawSaaS
- تخصصك: القوانين والتشريعات والأحكام اليمنية وإدارة مكاتب المحاماة
- لغتك: العربية الفصحى بأسلوب مهني واضح ومباشر

## قواعد صارمة:
1. أنت متخصص فقط في:
   - القوانين والتشريعات اليمنية (قانون العمل، الأحوال الشخصية، العقوبات، المدني، التجاري، الإجراءات الجزائية، الإيجارات، وغيرها)
   - الاستشارات القانونية العامة المتعلقة بالقانون اليمني
   - إجراءات المحاكم والتقاضي في اليمن
   - حقوق وواجبات الأطراف في القانون اليمني
   - شرح كيفية استخدام منصة LawSaaS وواجهاتها

2. إذا سُئلت سؤالاً خارج نطاق القانون والمحاماة وإدارة المكاتب القانونية:
   - اعتذر بلطف واحترافية
   - وضّح أنك مساعد قانوني متخصص فقط
   - اقترح على المستخدم طرح سؤال قانوني

3. عند الإجابة على سؤال قانوني:
   - اذكر المواد القانونية ذات الصلة إن أمكن (مثال: المادة 55 من قانون العمل رقم 5 لسنة 1995)
   - كن دقيقاً وموثوقاً
   - إذا لم تكن متأكداً 100%، وضّح ذلك وانصح بمراجعة محامٍ مختص
   - استخدم الترقيم والتنسيق لتسهيل القراءة

4. أسلوب الرد:
   - مختصر ومباشر (لا تطل في المقدمات)
   - استخدم الرموز التوضيحية: ⚖️ 📌 📜 ✅ ⚠️
   - استخدم **النص الغامق** للنقاط المهمة
   - أضف تنبيه "هذه المعلومات للاسترشاد فقط" في نهاية الإجابات القانونية المهمة

## معلومات عن المنصة (LawSaaS):
المنصة تحتوي على الواجهات التالية:
- لوحة التحكم: إحصائيات عامة عن المكتب
- القضايا: إدارة وتتبع القضايا (إضافة، تعديل، حذف، بحث)
- الجلسات: جدولة ومتابعة جلسات المحاكم
- الموكلين: إدارة بيانات العملاء والموكلين
- المالية: إيرادات ومصروفات وأتعاب المكتب
- المهام: إنشاء وتتبع المهام والواجبات
- التقويم: عرض المواعيد والجلسات بشكل مرئي
- الخط الزمني: تتبع سير القضية زمنياً
- التقارير: توليد تقارير مالية وتقارير أداء
- المراجع القانونية: حفظ السوابق والمراجع القضائية
- إدارة الفريق: إضافة موظفين وتحديد صلاحياتهم
- المساعد الذكي: أنت! المساعد القانوني وصياغة المستندات
"""


class GeminiLegalAssistant:
    """
    مساعد قانوني يمني ذكي مبني على Gemini API (google-genai SDK).
    يجيب على الأسئلة القانونية، أسئلة النظام،
    ويعتذر بأدب عن الأسئلة الخارجة عن النطاق.
    """

    def __init__(self):
        self._client = None
        self._available = False
        self._init_error = None
        self._initialize()

    def _initialize(self):
        """تهيئة الاتصال بـ Gemini API"""
        try:
            api_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if not api_key:
                # محاولة قراءة من .env مباشرة
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
            logger.info("✅ Gemini Legal Assistant initialized successfully (google-genai SDK)")

        except ImportError:
            self._init_error = "مكتبة google-genai غير مثبتة"
            logger.error(self._init_error)
        except Exception as e:
            self._init_error = f"خطأ في تهيئة Gemini: {str(e)}"
            logger.error(self._init_error)

    @property
    def is_available(self) -> bool:
        """هل الخدمة متاحة؟"""
        return self._available and self._client is not None

    def ask(
        self,
        question: str,
        local_context: Optional[str] = None,
        user_name: str = "",
    ) -> Optional[str]:
        """
        يرسل سؤال المستخدم إلى Gemini ويعيد الإجابة.

        Args:
            question: سؤال المستخدم
            local_context: سياق محلي (نتائج بحث قانوني، بيانات من النظام)
            user_name: اسم المستخدم

        Returns:
            نص الإجابة أو None في حالة الفشل
        """
        if not self.is_available:
            logger.warning(f"Gemini غير متاح: {self._init_error}")
            return None

        try:
            # بناء الرسالة مع السياق
            prompt_parts = []

            if user_name:
                prompt_parts.append(f"المستخدم: {user_name}")

            if local_context:
                prompt_parts.append(
                    f"--- معلومات مرجعية من قاعدة البيانات المحلية ---\n"
                    f"{local_context}\n"
                    f"--- نهاية المعلومات المرجعية ---\n"
                )
                prompt_parts.append(
                    "استخدم المعلومات المرجعية أعلاه إن كانت ذات صلة بالسؤال. "
                    "إذا كانت غير كافية، أجب من معرفتك القانونية."
                )

            prompt_parts.append(f"سؤال المستخدم: {question}")

            full_prompt = "\n\n".join(prompt_parts)

            # إرسال لـ Gemini باستخدام google-genai SDK
            response = self._client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "temperature": 0.4,
                    "top_p": 0.9,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                },
            )

            if response and response.text:
                return response.text.strip()

            return None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"خطأ في Gemini API: {error_msg}")
            
            # إذا كان خطأ حصة (quota), نسجل رسالة واضحة
            if "quota" in error_msg.lower() or "429" in error_msg:
                logger.error("⚠️ تجاوزت حصة Gemini API المجانية. قد تحتاج لانتظار دقيقة أو ترقية الخطة.")
            
            return None


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
