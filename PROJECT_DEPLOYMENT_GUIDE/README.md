# 📚 PROJECT_DEPLOYMENT_GUIDE
## مكتبة أدلة إدارة ونشر منصة LawSaaS (وزيرك - Waziruk)

> **للمطور:** هذا المجلد هو مرجعك الدائم لكل ما يتعلق برفع التحديثات وإدارة الاستضافة وحماية البيانات.  
> **المستودع الرسمي:** `https://github.com/ABOOD7333/law_firm_saas`  
> **السيرفر الحي:** `https://waziruk.tech` (IP: `179.198.198.38`)

---

## 🗂️ فهرس الملفات (6 أدلة شاملة بصيغة PDF)

| الرقم | اسم الملف | الوصف | الحجم |
|:---:|:---|:---|:---:|
| 01 | [01_Git_and_GitHub_Guide.pdf](./01_Git_and_GitHub_Guide.pdf) | الدليل الشامل لـ Git وGitHub من الصفر: الفرق بينهما، دورة حياة الملفات، الفروع، وحل الأخطاء. | ~352 KB |
| 02 | [02_Upload_Project_to_GitHub.pdf](./02_Upload_Project_to_GitHub.pdf) | التطبيق العملي خطوة بخطوة على مستودع `ABOOD7333/law_firm_saas` مع Feature Branch Workflow. | ~287 KB |
| 03 | [03_Deploy_Project_to_Hosting.pdf](./03_Deploy_Project_to_Hosting.pdf) | النشر والاستضافة على السيرفر الفعلي: SSH، Docker، Nginx، متغيرات البيئة، ومراقبة السجلات. | ~546 KB |
| 04 | [04_Database_and_Backups.pdf](./04_Database_and_Backups.pdf) | إدارة قواعد البيانات PostgreSQL: الترقية التلقائية، النسخ الاحتياطي، الاسترجاع، وحماية بيانات المكاتب. | ~262 KB |
| 05 | [05_Troubleshooting_and_Rollback.pdf](./05_Troubleshooting_and_Rollback.pdf) | استكشاف الأعطال: أخطاء 500/502، الـ Rollback الفوري، وحل أشهر 5 مشاكل في النشر. | ~353 KB |
| 06 | [06_Daily_Workflow.pdf](./06_Daily_Workflow.pdf) | بطاقة العمل اليومية (Cheat Sheet): 8 خطوات مرتبة من فتح المشروع حتى اختبار الموقع الحي. | ~293 KB |

---

## ⚡ الأوامر الحيوية السريعة (Quick Reference)

### على جهازك المحلي (Windows PowerShell):
```bash
# فحص حالة التعديلات
git status

# رفع تحديث كامل دفعة واحدة
git add .
git commit -m "وصف التحديث"
git pull origin main
git push origin main
```

### على السيرفر الفعلي (عبر SSH):
```bash
# الاتصال بالسيرفر
ssh root@179.198.198.38

# نشر آخر تحديث
cd /opt/lawsaas
git pull origin main
docker compose up -d --build app

# مراقبة السجلات
docker logs -f --tail 50 lawsaas_app

# إعادة تشغيل سريع
docker restart lawsaas_app
```

---

## 🛡️ قواعد الأمان الذهبية (لا تنسها أبداً)

1. **لا ترفع ملف `.env` أبداً إلى GitHub** — يحتوي على كلمات المرور والمفاتيح السرية.
2. **لا ترفع ملف `law_firm.db`** — يحتوي على بيانات العملاء والقضايا الحقيقية.
3. **قبل كل Push**: تأكد من `git status` أن الملفات الحساسة ليست في القائمة.
4. **استخدم الحذف الآمن دائماً**: `is_deleted = 1` بدلاً من `db.delete()`.
5. **كل استعلام يجب أن يتضمن**: `office_id == user.office_id` لعزل بيانات المكاتب.

---

## 🔄 دورة العمل في دقيقتين

```
تعديل الكود محلياً
        ↓
git add . && git commit -m "..."
        ↓
git push origin main
        ↓
SSH إلى السيرفر → git pull → docker compose up -d --build app
        ↓
docker logs → افتح waziruk.tech → تأكد من عمل الميزة ✅
```

---

*تم إعداد هذا الدليل بناءً على الإعدادات الفعلية لمشروع LawSaaS — نوفمبر 2026*
