# ================================================
# LawSaaS — Dockerfile (Multi-stage Build)
# ================================================

# --- المرحلة 1: بناء التبعيات ---
FROM python:3.11-slim AS builder

# منع Python من كتابة ملفات .pyc وتأخير الـ output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# نثبت التبعيات أولاً (layer caching — أسرع في rebuilds)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# --- المرحلة 2: الصورة النهائية (أصغر حجم) ---
FROM python:3.11-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

# مستخدم غير جذر (security best practice)
RUN groupadd --gid 1001 lawsaas && \
    useradd --uid 1001 --gid lawsaas --shell /bin/bash --create-home lawsaas

WORKDIR /app

# نسخ التبعيات المبنية من المرحلة الأولى
COPY --from=builder /install /usr/local

# نسخ كود التطبيق
COPY --chown=lawsaas:lawsaas . .

# إنشاء مجلدات الرفع مع صلاحيات صحيحة
RUN mkdir -p static/uploads/documents static/css static/js static/img && \
    chown -R lawsaas:lawsaas static/

# التبديل للمستخدم غير الجذر
USER lawsaas

# المنفذ الذي يستمع عليه التطبيق
EXPOSE 8000

# فحص صحة الحاوية
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# أمر التشغيل
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
