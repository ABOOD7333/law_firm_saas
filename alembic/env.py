"""
Alembic Environment Configuration — LawSaaS
يقرأ DATABASE_URL من ملف .env تلقائياً
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# تحميل متغيرات البيئة من ملف .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # إذا لم يكن python-dotenv مثبتاً

# Alembic Config object
config = context.config

# تهيئة الـ logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# استيراد موديلات قاعدة البيانات للـ autogenerate
# يجب استيراد كل الموديلات هنا حتى يتعرف عليها Alembic
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import Base

target_metadata = Base.metadata

# قراءة DATABASE_URL من متغيرات البيئة
def get_database_url():
    url = os.getenv("DATABASE_URL", "sqlite:///./law_firm.db")
    # Heroku/Render يعطي postgres:// لكن SQLAlchemy يريد postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def run_migrations_offline() -> None:
    """
    وضع Offline: يولد ملف SQL بدل تنفيذ مباشر.
    مفيد لمراجعة التغييرات قبل تطبيقها على الإنتاج.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # مطلوب لـ SQLite ALTER TABLE
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    وضع Online: تنفيذ migrations مباشرة على قاعدة البيانات.
    """
    # نضع DATABASE_URL في config
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # مطلوب لـ SQLite ALTER TABLE
            compare_type=True,      # يكتشف تغيير نوع العمود
            compare_server_default=True,  # يكتشف تغيير القيمة الافتراضية
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
