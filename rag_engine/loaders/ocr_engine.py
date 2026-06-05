"""
Arabic OCR Engine for Legal Documents
يستخرج النصوص العربية من الصور والمستندات الممسوحة ضوئياً باستخدام Tesseract
"""
import os
import pytesseract
from PIL import Image
import pdf2image
from pathlib import Path
from ..config import TESSERACT_CMD, POPPLER_PATH

# Configure Tesseract path for Windows
if os.name == 'nt' and os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

class ArabicOCREngine:
    def __init__(self):
        # We use 'ara' for Arabic and 'eng' for mixed English (e.g. numbers, emails)
        self.lang = 'ara+eng'

    def extract_text_from_image(self, image_path: str) -> str:
        """يستخرج النص من صورة واحدة"""
        try:
            img = Image.open(image_path)
            # Custom config to improve Arabic extraction
            custom_config = r'--oem 3 --psm 6 --tessdata-dir "' + str(Path(__file__).resolve().parent.parent / 'tessdata') + '"'
            text = pytesseract.image_to_string(img, lang=self.lang, config=custom_config)
            return self._clean_arabic_text(text)
        except Exception as e:
            return f"Error extracting text from image: {str(e)}"

    def extract_text_from_scanned_pdf(self, pdf_path: str) -> str:
        """يحول ملف PDF ممسوح ضوئياً إلى صور ثم يستخرج النص"""
        try:
            # Note: poppler must be installed and in PATH for pdf2image to work
            images = pdf2image.convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
            full_text = []
            
            for i, img in enumerate(images):
                custom_config = r'--oem 3 --psm 6 --tessdata-dir "' + str(Path(__file__).resolve().parent.parent / 'tessdata') + '"'
                page_text = pytesseract.image_to_string(img, lang=self.lang, config=custom_config)
                full_text.append(f"--- صفحة {i+1} ---\n{page_text}")
                
            return self._clean_arabic_text("\n".join(full_text))
        except Exception as e:
            return f"Error processing scanned PDF: {str(e)}\nMake sure Poppler is installed."

    def _clean_arabic_text(self, text: str) -> str:
        """ينظف النص العربي المستخرج من الـ OCR لإزالة الأخطاء الشائعة"""
        if not text:
            return ""
        # Remove multiple newlines
        text = '\n'.join([line.strip() for line in text.split('\n') if line.strip()])
        # Basic cleanup for common OCR artifacts could go here
        return text

# Singleton instance
ocr_engine = ArabicOCREngine()
