"""
Database-backed Rate Limiter — LawSaaS Platform
يخزن محاولات تسجيل الدخول في قاعدة البيانات بدلاً من الرام.
يعمل بشكل صحيح مع عدة Workers ويحافظ على البيانات عند إعادة التشغيل.
"""
import time
from sqlalchemy import text


def _get_db_connection():
    """Get a raw DB connection for rate limiting (lightweight, no ORM overhead)."""
    from database.database import engine
    return engine.connect()


def _ensure_rate_limit_table():
    """Create rate_limit_attempts table if it doesn't exist."""
    from database.database import engine
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rate_limit_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                attempt_type TEXT NOT NULL DEFAULT 'login',
                attempted_at REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rate_limit_ip_type 
            ON rate_limit_attempts(ip_address, attempt_type)
        """))


# تهيئة الجدول عند أول import
try:
    _ensure_rate_limit_table()
except Exception:
    pass  # سيتم إنشاؤه لاحقاً عند أول استخدام


def record_attempt(ip: str, attempt_type: str = "login"):
    """يسجل محاولة تسجيل دخول لعنوان IP."""
    try:
        from database.database import engine
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO rate_limit_attempts (ip_address, attempt_type, attempted_at) VALUES (:ip, :atype, :ts)"),
                {"ip": ip, "atype": attempt_type, "ts": time.time()}
            )
    except Exception as e:
        print(f"[RateLimiter] Error recording attempt: {e}")


def get_recent_attempts(ip: str, attempt_type: str = "login", window_seconds: int = 300) -> int:
    """يحسب عدد المحاولات خلال النافذة الزمنية المحددة."""
    try:
        from database.database import engine
        cutoff = time.time() - window_seconds
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM rate_limit_attempts WHERE ip_address = :ip AND attempt_type = :atype AND attempted_at > :cutoff"),
                {"ip": ip, "atype": attempt_type, "cutoff": cutoff}
            )
            return result.scalar() or 0
    except Exception as e:
        print(f"[RateLimiter] Error getting attempts: {e}")
        return 0


def is_rate_limited(ip: str, attempt_type: str = "login", max_attempts: int = 10, window_seconds: int = 300) -> bool:
    """يتحقق هل عنوان IP محظور مؤقتاً بسبب كثرة المحاولات."""
    return get_recent_attempts(ip, attempt_type, window_seconds) >= max_attempts


def cleanup_old_attempts(older_than_seconds: int = 3600):
    """ينظف المحاولات القديمة لمنع تراكم البيانات."""
    try:
        from database.database import engine
        cutoff = time.time() - older_than_seconds
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM rate_limit_attempts WHERE attempted_at < :cutoff"),
                {"cutoff": cutoff}
            )
    except Exception as e:
        print(f"[RateLimiter] Error cleaning up: {e}")
