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
    try:
        Base.metadata.create_all(bind=engine)
        print("[Database] create_all completed successfully.")
    except Exception:
        # Do not print the connection URL or driver exception (which may embed
        # deployment credentials). A partially initialized app must not start.
        raise RuntimeError("Database schema initialization failed; startup aborted") from None

    
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
            conn.execute(text("ALTER TABLE law_clients ADD COLUMN user_id INTEGER;"))
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
            conn.execute(text("ALTER TABLE law_offices ADD COLUMN disabled_modules_json TEXT DEFAULT '[]';"))
    except Exception:
        pass
    # Add new litigation and outcome fields to law_cases if not exists
    new_case_cols = [
        ('litigation_level_key', 'TEXT'),
        ('court_name', 'TEXT'),
        ('court_case_number', 'TEXT'),
        ('judgment_number', 'TEXT'),
        ('judgment_date', 'TEXT'),
        ('appeal_status', 'TEXT'),
        ('stage_start_date', 'TEXT'),
        ('outcome_key', 'TEXT')
    ]
    for col_name, col_type in new_case_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_cases ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass
    # Add new comprehensive hearing report fields to law_hearings if not exists
    new_hearing_cols = [
        ('report_number', 'TEXT'),
        ('court_name', 'TEXT'),
        ('court_case_number', 'TEXT'),
        ('litigation_level', 'TEXT'),
        ('hearing_time', 'TEXT'),
        ('judge_name', 'TEXT'),
        ('hearing_type', 'TEXT'),
        ('attendees_json', 'TEXT'),
        ('hearing_summary', 'TEXT'),
        ('client_requests', 'TEXT'),
        ('opponent_requests', 'TEXT'),
        ('pleadings_submitted', 'TEXT'),
        ('evidence_submitted', 'TEXT'),
        ('internal_notes', 'TEXT'),
        ('has_court_decision', 'INTEGER DEFAULT 0'),
        ('decision_type', 'TEXT'),
        ('decision_text', 'TEXT'),
        ('has_judgment', 'INTEGER DEFAULT 0'),
        ('judgment_number', 'TEXT'),
        ('judgment_date', 'TEXT'),
        ('post_hearing_actions', 'TEXT'),
        ('has_next_hearing', 'INTEGER DEFAULT 0'),
        ('postponement_reason', 'TEXT'),
        ('next_hearing_requirements', 'TEXT'),
        ('attachments_json', 'TEXT'),
        ('report_status', "TEXT DEFAULT 'approved'")
    ]
    for col_name, col_type in new_hearing_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_hearings ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Add comprehensive DMS fields to law_documents if not exists
    new_document_cols = [
        ('doc_code', 'TEXT'),
        ('client_id', 'INTEGER'),
        ('received_date', 'TEXT'),
        ('description', 'TEXT'),
        ('keywords', 'TEXT'),
        ('internal_notes', 'TEXT'),
        ('file_size', 'INTEGER'),
        ('file_type', 'TEXT'),
        ('is_archived', 'INTEGER DEFAULT 0'),
        ('archived_at', 'TEXT'),
        ('created_by_user_id', 'INTEGER'),
        ('updated_by_user_id', 'INTEGER')
    ]
    for col_name, col_type in new_document_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_documents ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass


        
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE access_profiles ADD COLUMN is_2fa_enabled INTEGER DEFAULT 0;"))
    except Exception:
        pass
        
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE access_profiles ADD COLUMN is_superadmin INTEGER DEFAULT 0;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE access_profiles ADD COLUMN locked_until TEXT;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE access_profiles ADD COLUMN permissions_json TEXT;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE access_profiles ADD COLUMN username TEXT;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE access_profiles ADD COLUMN linked_owner_id INTEGER;"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_hearings ADD COLUMN chamber_number TEXT;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_hearings ADD COLUMN floor_number TEXT;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_hearings ADD COLUMN show_in_client_portal INTEGER DEFAULT 1;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_tasks ADD COLUMN kanban_order INTEGER DEFAULT 0;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_tasks ADD COLUMN is_active INTEGER DEFAULT 1;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_tasks ADD COLUMN is_deleted INTEGER DEFAULT 0;"))
    except Exception:
        pass

    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE law_tasks ADD COLUMN priority_level INTEGER DEFAULT 2;"))
    except Exception:
        pass

    # Never log DATABASE_URL: it may contain a username and password.
    print(f"[Database] Connected using dialect: {engine.dialect.name}")
    print(f"[Database] Tables initialized successfully.")
