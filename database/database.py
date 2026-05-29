"""
Database Configuration — LawSaaS
يقرأ DATABASE_URL من ملف .env تلقائياً عبر python-dotenv
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base
import os

# تحميل ملف .env — لكن لا يتغلب على متغيرات Railway (override=False)
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)  # Railway DATABASE_URL له الأولوية دائماً
except ImportError:
    pass  # في الإنتاج نستخدم متغيرات البيئة مباشرة

# رابط قاعدة البيانات — يقرأ من Railway أولاً (PostgreSQL)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./law_firm.db")

# إصلاح رابط Heroku/Render القديم (postgres:// → postgresql://)
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace(
        "postgres://", "postgresql://", 1
    )

# إعدادات المحرك حسب نوع قاعدة البيانات
is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

engine_kwargs = {}
if is_sqlite:
    # SQLite يحتاج check_same_thread=False مع FastAPI
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL — connection pool settings
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_pre_ping"] = True  # يتحقق أن الاتصال حي قبل استخدامه

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

# تفعيل Foreign Keys في SQLite (معطل افتراضياً!)
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")  # أداء أفضل مع التزامن
        cursor.close()

# مصنع الجلسات
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI Dependency — يُعطي جلسة قاعدة بيانات لكل Request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    ينشئ كل الجداول إذا لم تكن موجودة.
    يُستخدم عند أول تشغيل أو في بيئات جديدة.
    """
    Base.metadata.create_all(bind=engine)
    
    # محاولة إضافة الأعمدة الجديدة للتحديث التلقائي بدون تهيئة يدوية
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_clients ADD COLUMN username TEXT;"))
    except Exception:
        pass
    
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_offices ADD COLUMN subscription_plan TEXT DEFAULT 'trial';"))
    except Exception:
        pass
        
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_offices ADD COLUMN subscription_end TEXT;"))
    except Exception:
        pass
        
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_offices ADD COLUMN receipt_base64 TEXT;"))
            conn.execute(text("ALTER TABLE law_offices ADD COLUMN receipt_status TEXT;"))
    except Exception:
        pass
        
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE access_profiles ADD COLUMN is_2fa_enabled INTEGER DEFAULT 0;"))
    except Exception:
        pass
        
    print(f"[Database] Connected to: {SQLALCHEMY_DATABASE_URL.split('?')[0]}")
    print(f"[Database] Tables initialized successfully.")
