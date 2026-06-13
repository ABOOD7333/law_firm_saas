"""
Local Embedding Generator - Lazy Loading
يحول النصوص العربية إلى Vectors محلياً باستخدام Sentence-Transformers
دون الحاجة إلى اتصال بالإنترنت أو واجهات برمجة تطبيقات مدفوعة

تحسين: Lazy Loading — لا يُحمَّل النموذج إلا عند أول استخدام فعلي
لضمان عدم تأثير تحميل النموذج على سرعة بدء تشغيل الخادم
"""
from typing import List
from ..config import EMBEDDING_MODEL_NAME


class LocalEmbedder:
    def __init__(self):
        # Lazy loading: لا نحمل النموذج هنا بل عند أول استخدام
        self._model = None

    def _load_model(self):
        """تحميل النموذج عند الحاجة الفعلية (Lazy Load)"""
        if self._model is None:
            print(f"[Embedder] Loading embedding model: {EMBEDDING_MODEL_NAME}...")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
                print(f"[Embedder] Model loaded successfully.")
            except Exception as e:
                print(f"[Embedder] Failed to load model: {e}")
                raise
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """يحول نص واحد إلى Vector"""
        model = self._load_model()
        return model.encode(text).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """يحول قائمة من النصوص إلى Vectors (أسرع للكميات الكبيرة)"""
        model = self._load_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()


# Singleton instance — لا يُحمَّل النموذج الآن، بل عند أول embed_text/embed_batch
embedder = LocalEmbedder()
