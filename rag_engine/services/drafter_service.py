"""
Legal Drafter Service
خدمة الصياغة القانونية تعتمد إما على القوالب الثابتة (مثلما بنينا سابقاً) أو LLM المحلي
"""
import requests
from ..config import USE_LOCAL_LLM, OLLAMA_API_URL, OLLAMA_MODEL

class LegalDrafter:
    
    def draft_document(self, doc_type: str, details: dict) -> str:
        """يصيغ مستنداً قانونياً"""
        if USE_LOCAL_LLM:
            return self._draft_with_ollama(doc_type, details)
        else:
            return self._draft_fallback(doc_type, details)

    def _draft_with_ollama(self, doc_type: str, details: dict) -> str:
        details_str = "\n".join([f"- {k}: {v}" for k, v in details.items()])
        prompt = f"""أنت محامٍ يمني محترف. طلب منك صياغة '{doc_type}' بناءً على المعطيات التالية:

{details_str}

الرجاء كتابة المستند بالصيغة القانونية اليمنية الصحيحة، وبشكل رسمي:"""
        
        try:
            response = requests.post(
                OLLAMA_API_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=180
            )
            if response.status_code == 200:
                return response.json().get('response', '')
            return f"حدث خطأ: {response.text}"
        except Exception as e:
            return f"تعذر الاتصال بالـ LLM: {str(e)}"

    def _draft_fallback(self, doc_type: str, details: dict) -> str:
        """يستخدم القوالب القديمة (الموجودة في ai_engine) إذا لم يكن هناك LLM"""
        # Here we would normally import the template generator from ai_engine
        # For now, we return a simple placeholder.
        return f"نموذج صياغة ({doc_type}) عبر القوالب الثابتة لعدم تفعيل Ollama.\n\nالمعطيات المدخلة:\n{details}"

drafter_service = LegalDrafter()
