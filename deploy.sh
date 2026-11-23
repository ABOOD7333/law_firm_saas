#!/bin/bash
# ========================================================
# LawSaaS Auto-Deploy Script for Hostinger VPS (Production)
# ========================================================
set -e

PROJECT_DIR="/var/www/law_firm1"
SERVICE_NAME="lawsaas"

echo "=== [$(date)] بدء عملية النشر الآلي للسيرفر ==="

# الانتقال لمجلد المشروع
cd "$PROJECT_DIR" || exit 1

# جلب أحدث التعديلات من الفرع الرئيسي
echo "--> جلب التحديثات من GitHub..."
git fetch origin main
git reset --hard origin/main

# تفعيل البيئة وتثبيت أي مكتبات جديدة إن وُجدت
if [ -d "venv" ]; then
    echo "--> تحديث البيئة الافتراضية..."
    source venv/bin/activate
    pip install -r requirements.txt --quiet
fi

# تشغيل الـ Migrations لقاعدة البيانات إن وُجدت تعديلات
echo "--> فحص وتطبيق migrations قاعدة البيانات..."
alembic upgrade head 2>&1 || true

# إعادة تشغيل خدمة التطبيق لتطبيق الكود الجديد فوراً
echo "--> إعادة تشغيل خدمة $SERVICE_NAME..."
if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl restart "$SERVICE_NAME"
elif command -v pm2 >/dev/null 2>&1; then
    pm2 reload "$SERVICE_NAME" || pm2 restart "$SERVICE_NAME"
fi

echo "=== [$(date)] اكتمل النشر بنجاح وتم تفعيل التعديلات! ==="
