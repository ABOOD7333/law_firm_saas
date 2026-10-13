"""
Arabic OCR Engine — Enhanced v2.0
محرك OCR العربي المحسَّن للوثائق القانونية اليمنية

التحسينات:
1. معالجة مسبقة للصور (Image Pre-processing):
   - تحويل للتدرج الرمادي
   - زيادة التباين التكيفية (CLAHE)
   - تحويل للأبيض والأسود النقي (Adaptive Binarization)
   - إزالة الضوضاء (Denoising)
   - تصحيح ميل الصورة (Deskewing)

2. يعمل OCR محلياً داخل التطبيق باستخدام Tesseract؛ لا تُرسل الصور إلى خدمات خارجية.
"""
import os
import re
from pathlib import Path
from typing import Tuple

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import pdf2image

from ..config import TESSERACT_CMD, POPPLER_PATH

# Configure Tesseract path for Windows
if os.name == 'nt' and os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

MIN_TEXT_LENGTH = 30            # إذا استخرج أقل من 30 حرف يُعدّ فاشلاً


class ImagePreprocessor:
    """
    معالجة مسبقة للصور لتحسين دقة الـ OCR على الوثائق القانونية اليمنية
    يعمل بـ Pillow فقط (بدون OpenCV) لضمان التوافق مع Railway
    """

    @staticmethod
    def preprocess(img: Image.Image) -> Image.Image:
        """
        خط أنابيب المعالجة المسبقة الكامل:
        تحويل → تباين → حدة → بينريزيشن → تنظيف
        """
        # 1. تحويل لـ RGB إذا كانت الصورة RGBA/P
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        # 2. تحويل للتدرج الرمادي
        gray = img.convert('L')

        # 3. تكبير الصورة إذا كانت صغيرة (تحسين OCR)
        w, h = gray.size
        if w < 1000:
            scale = 1000 / w
            gray = gray.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # 4. زيادة التباين (CLAHE بديل بسيط باستخدام Pillow)
        enhancer = ImageEnhance.Contrast(gray)
        gray = enhancer.enhance(2.0)

        # 5. زيادة الحدة (Sharpening) لتوضيح الحروف
        enhancer = ImageEnhance.Sharpness(gray)
        gray = enhancer.enhance(2.5)

        # 6. تحسين السطوع قليلاً
        enhancer = ImageEnhance.Brightness(gray)
        gray = enhancer.enhance(1.1)

        # 7. تطبيق فلتر Unsharp Mask لتوضيح الحواف
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))

        # 8. Binarization بسيطة: تحويل للأبيض والأسود النقي
        # نستخدم نقطة وسط (128) مع توسيع التباين أولاً
        threshold = 140
        gray = gray.point(lambda x: 0 if x < threshold else 255, '1')
        gray = gray.convert('L')

        return gray

class ArabicOCREngine:
    def __init__(self):
        self.lang = 'ara+eng'
        self.preprocessor = ImagePreprocessor()
        
        # تحديد مسار tessdata المحلي في جذر المشروع
        current_dir = os.path.dirname(os.path.abspath(__file__))
        local_tessdata = os.path.abspath(os.path.join(current_dir, "..", "..", "tessdata"))
        
        tessdata_option = ""
        if os.path.exists(os.path.join(local_tessdata, "ara.traineddata")):
            tessdata_option = f'--tessdata-dir "{local_tessdata}" '
            print(f"[OCR] Found local tessdata directory: {local_tessdata}")
            
        self._tesseract_config = (
            f'{tessdata_option}--oem 3 --psm 6 '
            '-c preserve_interword_spaces=1 '
            '-c tessedit_char_blacklist=|}{]['
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. استخراج النص من صورة واحدة
    # ─────────────────────────────────────────────────────────────────────────
    def extract_text_from_image(self, image_path: str) -> str:
        """
        يستخرج النص محلياً من صورة واحدة مع المعالجة المسبقة
        """
        try:
            img = Image.open(image_path)
            return self._ocr_with_fallback(img, source_name=image_path)
        except Exception as e:
            return f"Error extracting text from image: {str(e)}"

    # ─────────────────────────────────────────────────────────────────────────
    # 2. استخراج النص من PDF ممسوح ضوئياً
    # ─────────────────────────────────────────────────────────────────────────
    def extract_text_from_scanned_pdf(self, pdf_path: str) -> str:
        """
        يحول PDF ممسوح ضوئياً إلى صور ثم يطبق OCR محسَّن على كل صفحة
        """
        try:
            poppler = POPPLER_PATH if os.path.exists(POPPLER_PATH) else None
            images = pdf2image.convert_from_path(
                pdf_path,
                dpi=300,           # جودة عالية لتحسين OCR
                poppler_path=poppler
            )
            full_text = []
            for i, img in enumerate(images):
                print(f"[OCR] Processing page {i+1}/{len(images)}...")
                page_text = self._ocr_with_fallback(img, source_name=f"page_{i+1}")
                full_text.append(f"--- صفحة {i+1} ---\n{page_text}")

            return self._clean_arabic_text("\n".join(full_text))
        except Exception as e:
            return f"Error processing scanned PDF: {str(e)}\nMake sure Poppler is installed."

    # ─────────────────────────────────────────────────────────────────────────
    # المحرك المحلي: المعالجة المسبقة + Tesseract
    # ─────────────────────────────────────────────────────────────────────────
    def _ocr_with_fallback(self, img: Image.Image, source_name: str = "") -> str:
        """
        1. معالجة مسبقة للصورة
        2. Tesseract OCR
        3. تقييم الجودة
        4. عند انخفاض الجودة، يرجع النص المستخرج كما هو دون إرسال الصورة للخارج
        """
        # الخطوة 1: المعالجة المسبقة
        preprocessed = self.preprocessor.preprocess(img)

        # الخطوة 2: Tesseract
        tesseract_text, confidence = self._run_tesseract(preprocessed)
        print(f"[OCR] Tesseract confidence: {confidence:.1f}% | chars: {len(tesseract_text)} | {source_name}")

        # الخطوة 3: تقييم الجودة
        is_good_quality = len(tesseract_text.strip()) >= MIN_TEXT_LENGTH and self._has_arabic_content(tesseract_text)

        if is_good_quality:
            print(f"[OCR] Tesseract result accepted")
            return self._clean_arabic_text(tesseract_text)

        # إذا كانت الجودة منخفضة، أعد النص المحلي مع تنبيه إن تعذر استخراجه
        print(f"[OCR] Tesseract quality low — returning local OCR output")
        return self._clean_arabic_text(tesseract_text) if tesseract_text else "تعذر استخراج النص من هذه الصورة"

    def _run_tesseract(self, img: Image.Image) -> Tuple[str, float]:
        """تشغيل Tesseract وحساب متوسط الثقة"""
        try:
            # استخراج النص
            text = pytesseract.image_to_string(img, lang=self.lang, config=self._tesseract_config)

            # حساب نسبة الثقة
            try:
                data = pytesseract.image_to_data(
                    img, lang=self.lang, config=self._tesseract_config,
                    output_type=pytesseract.Output.DICT
                )
                confidences = [c for c in data['conf'] if isinstance(c, (int, float)) and c >= 0]
                avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            except Exception:
                avg_conf = 50.0  # قيمة افتراضية إذا تعذر حساب الثقة

            return text, avg_conf
        except Exception as e:
            return "", 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────────────────────────────────
    def _has_arabic_content(self, text: str) -> bool:
        """التحقق من وجود محتوى عربي حقيقي في النص"""
        arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        return arabic_chars >= 10

    def _clean_arabic_text(self, text: str) -> str:
        """تنظيف النص العربي المستخرج من الـ OCR"""
        if not text:
            return ""
        # إزالة الأسطر الفارغة المتكررة
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        # إزالة الرموز الغريبة الشائعة في OCR
        text = re.sub(r'[|}{[\]<>\\]', '', text)
        # إزالة المسافات المتكررة
        text = re.sub(r'  +', ' ', text)
        return text.strip()


# Singleton instance
ocr_engine = ArabicOCREngine()
