"""
PDF and Document Loader
يقرأ ملفات PDF والنصوص وDOCX ويستخرج النصوص منها
إذا كان الـ PDF ممسوحاً ضوئياً ولا يحتوي على نص، سيحوله تلقائياً إلى محرك الـ OCR
"""
import os
import pdfplumber
import docx
from .ocr_engine import ocr_engine

class DocumentLoader:
    
    @staticmethod
    def load_pdf(file_path: str) -> str:
        """قراءة الـ PDF النصي. إذا كان فارغاً (ممسوح ضوئياً)، يستخدم OCR"""
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            return f"Error reading PDF: {str(e)}"
            
        # إذا لم يتم استخراج أي نص، فهذا يعني أن الملف عبارة عن صور ممسوحة ضوئياً
        if not text.strip():
            print(f"[{file_path}] No text found. Switching to OCR...")
            return ocr_engine.extract_text_from_scanned_pdf(file_path)
            
        return text

    @staticmethod
    def load_docx(file_path: str) -> str:
        """استخراج النص من ملفات Word"""
        try:
            doc = docx.Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return '\n'.join(full_text)
        except Exception as e:
            return f"Error reading DOCX: {str(e)}"

    @staticmethod
    def load_txt(file_path: str) -> str:
        """قراءة ملف نصي"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading TXT: {str(e)}"
            
    @staticmethod
    def load_image(file_path: str) -> str:
        """قراءة صورة باستخدام OCR"""
        return ocr_engine.extract_text_from_image(file_path)

    @classmethod
    def load_file(cls, file_path: str) -> str:
        """دالة عامة تتعرف على الامتداد وتستدعي الدالة المناسبة"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return cls.load_pdf(file_path)
        elif ext == '.docx':
            return cls.load_docx(file_path)
        elif ext == '.txt':
            return cls.load_txt(file_path)
        elif ext in ['.png', '.jpg', '.jpeg']:
            return cls.load_image(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

document_loader = DocumentLoader()
