"""Helpers and approved categories for the Yemeni laws archive."""

import io
from typing import Optional


LEGAL_CATEGORIES = {
    "constitution": "الدستور اليمني",
    "civil_law": "القانون المدني",
    "criminal_law": "قانون الجرائم والعقوبات",
    "procedures_law": "قانون المرافعات والتنفيذ",
    "commercial_law": "القانون التجاري",
    "companies_law": "قانون الشركات",
    "labor_law": "قانون العمل",
    "family_law": "قانون الأحوال الشخصية",
    "investment_law": "قوانين الاستثمار والضرائب",
    "real_estate_law": "قوانين الأراضي والعقارات",
    "regulations": "اللوائح والقرارات التنفيذية",
    "other_yemeni_law": "قوانين ولوائح يمنية أخرى",
}

ALLOWED_LAW_TYPES = {"law", "regulation"}
ALLOWED_FILE_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_DOCX_ENTRIES = 2000
MAX_DOCX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_CHARS = 5_000_000


def extract_legal_text(data: bytes, extension: str) -> str:
    """Extract searchable text from common legal document formats, without AI."""
    extension = extension.lower()
    if extension == ".txt":
        result = data.decode("utf-8-sig", errors="replace").strip()
        if len(result) > MAX_EXTRACTED_CHARS:
            raise ValueError("النص المستخرج يتجاوز الحد المسموح")
        return result
    if extension == ".pdf":
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise ValueError("المستند يتجاوز الحد الأقصى لعدد الصفحات")
            parts = []
            size = 0
            for page in pdf.pages:
                part = page.extract_text() or ""
                size += len(part)
                if size > MAX_EXTRACTED_CHARS:
                    raise ValueError("النص المستخرج يتجاوز الحد المسموح")
                parts.append(part)
            return "\n".join(parts).strip()
    if extension == ".docx":
        import zipfile
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_ENTRIES or sum(item.file_size for item in members) > MAX_DOCX_EXPANDED_BYTES:
                raise ValueError("محتوى مستند Word يتجاوز الحدود الآمنة")
            if any(item.compress_size and item.file_size / item.compress_size > 200 for item in members):
                raise ValueError("نسبة ضغط غير آمنة داخل مستند Word")
        from docx import Document

        document = Document(io.BytesIO(data))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            paragraphs.extend(" | ".join(cell.text for cell in row.cells) for row in table.rows)
        result = "\n".join(paragraphs).strip()
        if len(result) > MAX_EXTRACTED_CHARS:
            raise ValueError("النص المستخرج يتجاوز الحد المسموح")
        return result
    return ""


def law_excerpt(text: Optional[str], query: str, limit: int = 360) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    lowered = text.casefold()
    position = lowered.find(query.casefold()) if query else -1
    start = max(0, position - limit // 3) if position >= 0 else 0
    excerpt = text[start:start + limit]
    return ("…" if start else "") + excerpt + ("…" if start + limit < len(text) else "")
