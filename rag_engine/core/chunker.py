"""
Semantic Text Chunker
يقوم بتقسيم النصوص القانونية الطويلة (مثل الدستور أو القوانين) إلى فقرات (Chunks) 
مترابطة دلالياً لضمان عدم قطع المعنى أثناء الاسترجاع
"""
import re
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ..config import CHUNK_SIZE, CHUNK_OVERLAP

class LegalTextChunker:
    def __init__(self):
        # نستخدم Langchain's RecursiveCharacterTextSplitter لأنه ممتاز في احترام الفقرات
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=[
                "\n\nمادة (", "\nمادة (", "\nالفصل", "\nالباب", # Legal specific separators
                "\n\n", "\n", " ", "" # Fallback standard separators
            ]
        )

    def chunk_text(self, text: str) -> List[str]:
        """يقوم بتقسيم النص إلى قائمة من الفقرات"""
        # تنظيف مبدئي
        text = self._clean_text(text)
        
        # تقسيم باستخدام LangChain
        chunks = self.text_splitter.split_text(text)
        
        return chunks
        
    def _clean_text(self, text: str) -> str:
        """تنظيف النص من المسافات الزائدة والفراغات"""
        # إزالة المسافات المتكررة
        text = re.sub(r' +', ' ', text)
        # إزالة الأسطر الفارغة المتعددة
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

chunker = LegalTextChunker()
