"""
RAG Engine Configuration
إعدادات محرك المعرفة القانونية RAG اليمني المتكامل
"""
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DATA_DIR = BASE_DIR / "knowledge_data"
VECTOR_DB_DIR = BASE_DIR / "chroma_db"

# Ensure directories exist
os.makedirs(VECTOR_DB_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DATA_DIR, exist_ok=True)

# ChromaDB Settings
CHROMA_COLLECTION_NAME = "yemeni_legal_knowledge"

# Embedding Model Settings
# Using a lightweight multilingual model that supports Arabic. 
# Runs locally, offline, no API key needed.
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-small" 

# Text Chunking Settings
CHUNK_SIZE = 1000      # Number of characters per chunk
CHUNK_OVERLAP = 200    # Overlap between chunks to maintain context

# Tesseract OCR Settings
# Windows path to Tesseract (if installed locally). Must be updated based on deployment.
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Poppler path for PDF to Image conversion
POPPLER_PATH = str(BASE_DIR.parent / "poppler" / "poppler-24.08.0" / "Library" / "bin")

# Local LLM Settings (Ollama / HuggingFace)
# Set to True if Ollama is running locally for summarization and drafting
USE_LOCAL_LLM = False
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3" # Or 'qwen:7b' for better Arabic

# Supported Document Types
SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]

# Legal Categories
LEGAL_CATEGORIES = {
    "constitution": "الدستور اليمني",
    "civil_law": "القانون المدني",
    "criminal_law": "القانون الجنائي",
    "procedures_law": "قانون المرافعات",
    "execution_law": "قانون التنفيذ",
    "commercial_law": "القانون التجاري",
    "companies_law": "قانون الشركات",
    "labor_law": "قانون العمل",
    "family_law": "قانون الأحوال الشخصية",
    "investment_law": "قانون الاستثمار",
    "tax_law": "قوانين الضرائب",
    "real_estate_law": "قوانين العقارات والأراضي",
    "regulations": "اللوائح والقرارات التنفيذية",
    "supreme_court": "أحكام المحكمة العليا",
    "appeal_court": "أحكام محاكم الاستئناف",
    "precedents": "السوابق القضائية",
    "principles": "المبادئ القضائية",
    "interpretations": "التفسيرات القانونية",
}
