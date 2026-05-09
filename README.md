# LawSaaS — نظام إدارة مكاتب المحاماة السحابي

نظام ويب متكامل لإدارة مكاتب المحاماة، مبني بـ FastAPI + SQLAlchemy.

---

## 🚀 التشغيل السريع (محلي)

### المتطلبات
- Python 3.11+
- pip

### الخطوات

```bash
# 1. استنساخ المشروع
git clone <repo-url>
cd law_firm1

# 2. إنشاء بيئة افتراضية
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# 3. تثبيت المكتبات
pip install -r requirements.txt

# 4. إعداد متغيرات البيئة
copy .env.example .env
# عدّل .env بمعلوماتك

# 5. تهيئة قاعدة البيانات
python -c "from database.database import init_db; init_db()"

# 6. تشغيل التطبيق
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

افتح المتصفح على: http://127.0.0.1:8000

---

## 🐳 التشغيل بـ Docker

```bash
# نسخ ملف البيئة
copy .env.example .env
# عدّل .env

# بناء وتشغيل
docker-compose up --build

# في الخلفية
docker-compose up -d --build

# إيقاف
docker-compose down
```

---

## 🗃️ إدارة قاعدة البيانات (Alembic)

```bash
# تطبيق أحدث migration
alembic upgrade head

# إنشاء migration جديد (بعد تعديل models.py)
alembic revision --autogenerate -m "اسم التغيير"

# عرض الحالة الحالية
alembic current

# التراجع عن آخر migration
alembic downgrade -1

# عرض كل migrations
alembic history --verbose
```

---

## 📁 هيكل المشروع

```
law_firm1/
├── main.py                 # نقطة الدخول
├── dependencies.py         # get_current_user, templates
├── email_service.py        # خدمة البريد الإلكتروني
├── requirements.txt        # المكتبات
├── .env                    # متغيرات البيئة (لا تُرفع لـ Git)
├── .env.example            # قالب متغيرات البيئة
├── alembic.ini             # إعدادات Alembic
├── Dockerfile              # Docker image
├── docker-compose.yml      # Docker Compose
├── database/
│   ├── database.py         # إعداد SQLAlchemy
│   └── models.py           # موديلات قاعدة البيانات
├── routers/                # FastAPI Routers
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JS, صور
└── alembic/
    ├── env.py              # إعداد Alembic
    └── versions/           # ملفات الـ migrations
```

---

## 🔐 الأمان

- كلمات المرور مشفرة بـ PBKDF2-SHA256 (260,000 iteration)
- جلسات آمنة بـ HttpOnly cookies
- CSRF Protection مفعّل
- قفل الحساب بعد 10 محاولات فاشلة
- عزل البيانات بـ `office_id` لكل عملية

---

## 🌐 النشر على السحابة (Render / Railway)

```bash
# 1. أضف DATABASE_URL في متغيرات البيئة على المنصة
# 2. أضف باقي متغيرات .env
# 3. Start Command:
uvicorn main:app --host 0.0.0.0 --port $PORT
```
