"""
Local Embedding Generator
يحول النصوص العربية إلى Vectors محلياً باستخدام Sentence-Transformers
دون الحاجة إلى اتصال بالإنترنت أو واجهات برمجة تطبيقات مدفوعة
"""
from typing import List
from sentence_transformers import SentenceTransformer
from ..config import EMBEDDING_MODEL_NAME

class LocalEmbedder:
    def __init__(self):
        print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
        # Note: First time running this, it will download the model (~100-300MB) from HuggingFace
        # After that, it runs completely offline.
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        
    def embed_text(self, text: str) -> List[float]:
        """يحول نص واحد إلى Vector"""
        # Return as a simple python list
        return self.model.encode(text).tolist()
        
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """يحول قائمة من النصوص إلى Vectors (أسرع للكميات الكبيرة)"""
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

# Singleton instance
embedder = LocalEmbedder()
