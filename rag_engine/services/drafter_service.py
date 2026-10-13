"""
Legal Drafter Service
خدمة الصياغة القانونية تعتمد إما على القوالب الثابتة (مثلما بنينا سابقاً) أو LLM المحلي
"""
from ai_engine.local_model import generate_local
from ..config import USE_LOCAL_LLM

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
            result = generate_local(prompt, timeout=180)
            return result or self._draft_fallback(doc_type, details)
        except Exception:
            return self._draft_fallback(doc_type, details)

    def _draft_fallback(self, doc_type: str, details: dict) -> str:
        """يستخدم القوالب القديمة (الموجودة في ai_engine) إذا لم يكن هناك LLM"""
        # Here we would normally import the template generator from ai_engine
        # For now, we return a simple placeholder.
        return f"نموذج صياغة ({doc_type}) عبر القوالب الثابتة لعدم تفعيل Ollama.\n\nالمعطيات المدخلة:\n{details}"

drafter_service = LegalDrafter()
