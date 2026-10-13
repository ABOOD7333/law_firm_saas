"""
Legal Summarizer Service
يقوم بتلخيص الأحكام والقضايا الطويلة باستخدام Local LLM (Ollama)
"""
from ai_engine.local_model import generate_local
from ..config import USE_LOCAL_LLM

class LegalSummarizer:
    
    def summarize(self, text: str) -> str:
        """يلخص النص القانوني"""
        if not text or len(text.strip()) < 50:
            return "النص قصير جداً ولا يحتاج للتلخيص."
            
        if USE_LOCAL_LLM:
            return self._summarize_with_ollama(text)
        else:
            return self._summarize_fallback(text)
            
    def _summarize_with_ollama(self, text: str) -> str:
        prompt = f"""أنت مستشار قانوني يمني خبير. قم بتلخيص النص القانوني التالي بشكل دقيق واحترافي، مع التركيز على الوقائع الرئيسية والنتيجة (إن وجدت):

النص:
{text}

الملخص:"""
        try:
            result = generate_local(prompt, timeout=120)
            return result or self._summarize_fallback(text)
        except Exception:
            return self._summarize_fallback(text)

    def _summarize_fallback(self, text: str) -> str:
        """
        في حال عدم توفر LLM، نستخدم طريقة استخلاصية بسيطة (Extractive)
        بأخذ أهم الجمل من البداية والنهاية
        """
        sentences = [s.strip() for s in text.replace('\n', '.').split('.') if len(s.strip()) > 20]
        if len(sentences) <= 3:
            return text
            
        summary = f"({len(sentences)} جملة تقريباً)\n\n"
        summary += "- " + sentences[0] + ".\n"
        summary += "- " + sentences[1] + ".\n"
        summary += "...\n"
        summary += "- " + sentences[-2] + ".\n"
        summary += "- " + sentences[-1] + ".\n"
        
        return "تم استخدام التلخيص الاستخلاصي البسيط (لعدم تفعيل Ollama):\n\n" + summary

summarizer_service = LegalSummarizer()
