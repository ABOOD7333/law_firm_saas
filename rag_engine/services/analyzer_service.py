"""
Contract Analyzer Service
يستخدم تقنيات الـ NLP والـ LLM المحلي (إذا توفر) لاستخراج البنود الهامة من العقود (أطراف، تواريخ، مبالغ)
"""
import re
from typing import Dict, Any

class ContractAnalyzer:
    def __init__(self):
        # We will use Regex rules for basic offline extraction if Local LLM is not available
        self.money_pattern = r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:ريال|دولار|يورو|جنيه))'
        self.date_pattern = r'(\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4})'
        # Very basic Arabic name extraction pattern (heuristic)
        self.party_pattern = r'(?:الطرف الأول|الطرف الثاني|السيد/|السادة/|المقاول/|المؤجر|المستأجر)\s*[:\-]?\s*([\w\s]+?)(?:الذي|ويحمل|بطاقة|الجنسية|\n)'

    def analyze_contract(self, text: str) -> Dict[str, Any]:
        """
        يحلل العقد ويستخرج المعلومات الأساسية
        """
        # في بيئة حقيقية بدون إنترنت، يتم استخدام Regex هنا، أو استدعاء Ollama
        
        # 1. Regex Fallback
        moneys = re.findall(self.money_pattern, text)
        dates = re.findall(self.date_pattern, text)
        parties = re.findall(self.party_pattern, text)
        
        # Clean parties
        parties = [p.strip() for p in parties if len(p.strip()) > 3]

        return {
            "parties": list(set(parties)),
            "dates": list(set(dates)),
            "financial_values": list(set(moneys)),
            "is_llm_used": False
        }

analyzer_service = ContractAnalyzer()
