"""
Database Configuration — LawSaaS
يقرأ DATABASE_URL من ملف .env تلقائياً عبر python-dotenv
"""
from sqlalchemy import create_engine, event, inspect, text as _sql_text
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

    # Preserve prior Yemeni-law documents, then remove the obsolete AI/RAG data.
    # Model output, chat transcripts, vector chunks, and quotas are intentionally dropped.
    try:
        legacy_categories = (
            "constitution", "civil_law", "criminal_law", "procedures_law",
            "execution_law", "commercial_law", "companies_law", "labor_law",
            "family_law", "investment_law", "tax_law", "real_estate_law", "regulations",
        )
        inspector = inspect(engine)
        if "rag_knowledge_documents" in inspector.get_table_names():
            with engine.begin() as conn:
                legacy_docs = conn.execute(_sql_text(
                    "SELECT id, file_name, file_path, file_type, category, created_at "
                    "FROM rag_knowledge_documents WHERE COALESCE(is_deleted, 0) = 0"
                )).mappings().all()
                for old in legacy_docs:
                    if old["category"] not in legacy_categories:
                        continue
                    already_migrated = conn.execute(_sql_text(
                        "SELECT 1 FROM yemeni_law_documents WHERE legacy_document_id = :legacy_id"
                    ), {"legacy_id": old["id"]}).first()
                    if already_migrated:
                        continue
                    old_type = old["file_type"] or ""
                    file_name = old["file_name"] or "تشريع يمني"
                    conn.execute(_sql_text(
                        "INSERT INTO yemeni_law_documents "
                        "(title, law_type, category, source_reference, legal_text, file_name, file_type, "
                        "legacy_file_path, legacy_document_id, created_at, is_deleted) "
                        "VALUES (:title, :law_type, :category, :source, '', :file_name, :file_type, "
                        ":file_path, :legacy_id, :created_at, 0)"
                    ), {
                        "title": file_name,
                        "law_type": "regulation" if old["category"] == "regulations" else "law",
                        "category": old["category"],
                        "source": "مستورد من مكتبة القوانين السابقة",
                        "file_name": file_name,
                        "file_type": old_type,
                        "file_path": old["file_path"],
                        "legacy_id": old["id"],
                        "created_at": old["created_at"],
                    })
                for obsolete_table in (
                    "rag_chunk_metadata", "rag_knowledge_documents",
                    "ai_chat_history", "ai_knowledge", "ai_user_quotas",
                ):
                    if obsolete_table in inspect(conn).get_table_names():
                        conn.execute(_sql_text(f"DROP TABLE {obsolete_table}"))
        else:
            with engine.begin() as conn:
                for obsolete_table in ("ai_chat_history", "ai_knowledge", "ai_user_quotas", "rag_chunk_metadata"):
                    if obsolete_table in inspect(conn).get_table_names():
                        conn.execute(_sql_text(f"DROP TABLE {obsolete_table}"))
        print("[Database] Obsolete AI/RAG data removed; Yemeni-law records retained.")
    except Exception:
        # A failed destructive migration must abort startup rather than leave the
        # application partially migrated or continue serving obsolete features.
        raise RuntimeError("Yemeni law library migration failed; startup aborted") from None

    
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

    # تجديد خطط المكاتب التجريبية المنتهية لضمان عمل واجهات النظام والمستخدمين التجريبيين دون حظر
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE law_offices SET subscription_plan = 'yearly', subscription_end = '2030-01-01 00:00:00', is_active = 1 WHERE is_active = 1 AND (subscription_plan = 'trial' OR subscription_end IS NULL OR subscription_end < '2027-01-01');"
            ))
    except Exception as e:
        print(f"[Database Auto-Renew] {e}")
    # إزالة حقول درجات التقاضي وبيانات المحكمة والنتائج من جدول law_cases نهائياً
    cols_to_drop = [
        'litigation_level_key',
        'court_name',
        'court_case_number',
        'judgment_number',
        'judgment_date',
        'appeal_status',
        'stage_start_date',
        'outcome_key'
    ]
    for col_name in cols_to_drop:
        try:
            with engine.begin() as conn:
                conn.execute(_sql_text(f"ALTER TABLE law_cases DROP COLUMN {col_name};"))
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
        ('report_status', "TEXT DEFAULT 'approved'"),
        ('minutes_type', "TEXT DEFAULT 'primary'"),
        ('minutes_date', 'TEXT'),
        ('session_type', 'TEXT'),
        ('court_decision', 'TEXT'),
        ('judge_head', 'TEXT'),
        ('court_secretary', 'TEXT'),
        ('prosecutor_name', 'TEXT'),
        ('bench_judges_json', 'TEXT'),
        ('prosecution_details_json', 'TEXT'),
        ('decision_attachments_json', 'TEXT'),
        ('submitted_papers_json', 'TEXT'),
        ('attendees_list_json', 'TEXT')
    ]
    for col_name, col_type in new_hearing_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_hearings ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Add judicial section fields to law_incoming_cases if not exists
    new_incoming_cols = [
        ('hijri_year', 'TEXT'),
        ('incoming_sequence', 'INTEGER'),
        ('case_subject', 'TEXT'),
        ('crime_classification', 'TEXT'),
        ('client_capacity', 'TEXT'),
        ('incoming_status_at_reception', 'TEXT'),
        ('prosecutor_member_name', 'TEXT'),
        ('prosecution_disposition', 'TEXT'),
        ('office_position_on_prosecution', 'TEXT'),
        ('final_case_path', 'TEXT'),
        ('court_judge_name', 'TEXT'),
        ('hearing_start_date', 'TEXT'),
        ('case_reserved_for_judgment_date', 'TEXT'),
        ('judgment_date', 'TEXT'),
        ('office_position_on_court', 'TEXT'),
        ('office_position_attachment_path', 'TEXT'),
        ('appeal_judgment_decision', 'TEXT'),
        ('office_position_on_appeal', 'TEXT'),
        ('appeal_decision_attachment_path', 'TEXT'),
        ('supreme_court_name', 'TEXT'),
        ('supreme_chamber', 'TEXT'),
        ('cassation_date', 'TEXT'),
        ('appeal_file_dispatch_date', 'TEXT'),
        ('supreme_court_decision', 'TEXT'),
        ('supreme_court_decision_attachment_path', 'TEXT'),
        ('challenged_appeal_judgment', 'TEXT'),
        ('office_position_on_supreme', 'TEXT'),
        ('office_position_supreme_attachment_path', 'TEXT'),
        ('execution_type', 'TEXT'),
        ('execution_subject', 'TEXT'),
        ('execution_authority_name', 'TEXT'),
        ('execution_actions_taken', 'TEXT'),
        ('office_position_on_execution', 'TEXT'),
        ('execution_attachment_path', 'TEXT'),
        ('assigned_lawyer_id', 'INTEGER')
    ]
    for col_name, col_type in new_incoming_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_incoming_cases ADD COLUMN {col_name} {col_type};"))
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

    # Add comprehensive litigation party fields to law_parties if not exists
    new_party_cols = [
        ('party_type', "TEXT DEFAULT 'individual'"),
        ('nationality', 'TEXT'),
        ('cr_number', 'TEXT'),
        ('legal_capacity', 'TEXT'),
        ('representation_status', 'TEXT'),
        ('alt_phone', 'TEXT'),
        ('city', 'TEXT'),
        ('national_address', 'TEXT'),
        ('service_method', 'TEXT'),
        ('lawyer_name', 'TEXT'),
        ('lawyer_phone', 'TEXT'),
        ('lawyer_license_no', 'TEXT'),
        ('poa_number', 'TEXT'),
        ('poa_date', 'TEXT'),
        ('conflict_status', "TEXT DEFAULT 'clear'"),
        ('internal_notes', 'TEXT')
    ]
    for col_name, col_type in new_party_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_parties ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Add enterprise client fields to law_clients if not exists
    new_client_cols = [
        ('client_type', "TEXT DEFAULT 'individual'"),
        ('nationality', 'TEXT'),
        ('cr_number', 'TEXT'),
        ('legal_rep_name', 'TEXT'),
        ('city', 'TEXT'),
        ('address', 'TEXT'),
        ('notes', 'TEXT'),
        ('portal_access', 'INTEGER DEFAULT 1')
    ]
    for col_name, col_type in new_client_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_clients ADD COLUMN {col_name} {col_type};"))
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

    # Migrations for LawJudgments
    judgment_cols = [
        ("decree_number", "TEXT"),
        ("chamber_name", "TEXT"),
        ("litigation_degree", "TEXT DEFAULT 'ابتدائي'"),
        ("judgment_type", "TEXT DEFAULT 'موضوعي'"),
        ("notification_date", "TEXT"),
        ("appeal_deadline_days", "INTEGER DEFAULT 30"),
        ("appeal_deadline_date", "TEXT"),
        ("awarded_amount", "REAL DEFAULT 0.0"),
        ("legal_fees_awarded", "REAL DEFAULT 0.0"),
        ("is_final", "INTEGER DEFAULT 0"),
        ("attachment_path", "TEXT")
    ]
    for col_name, col_type in judgment_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_judgments ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for LawNotes (Communications & Notes)
    note_cols = [
        ("communication_channel", "TEXT DEFAULT 'internal_note'"),
        ("direction", "TEXT DEFAULT 'outbound'"),
        ("contact_person", "TEXT"),
        ("call_duration_minutes", "INTEGER DEFAULT 0"),
        ("is_billable", "INTEGER DEFAULT 0"),
        ("hourly_rate", "REAL DEFAULT 0.0"),
        ("is_pinned", "INTEGER DEFAULT 0"),
        ("is_client_visible", "INTEGER DEFAULT 0"),
        ("priority_level", "TEXT DEFAULT 'عادي'"),
        ("author_id", "INTEGER"),
        ("attachment_path", "TEXT")
    ]
    for col_name, col_type in note_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_notes ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for LawCorrespondences (Inbound & Outbound Registry)
    corr_cols = [
        ("registry_number", "TEXT"),
        ("entity_name", "TEXT"),
        ("recipient_name", "TEXT"),
        ("delivery_method", "TEXT"),
        ("tracking_number", "TEXT"),
        ("urgency_level", "TEXT DEFAULT 'عادي'"),
        ("confidentiality_level", "TEXT DEFAULT 'عادي'"),
        ("in_reply_to_id", "INTEGER"),
        ("attachment_path", "TEXT"),
        ("proof_of_delivery_path", "TEXT"),
        ("created_by_user_id", "INTEGER")
    ]
    for col_name, col_type in corr_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_correspondences ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for LawWorkflowRules (Smart Automation Engine)
    workflow_cols = [
        ("category", "TEXT DEFAULT 'general'"),
        ("description", "TEXT"),
        ("execution_count", "INTEGER DEFAULT 0"),
        ("last_triggered_at", "TEXT")
    ]
    for col_name, col_type in workflow_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_workflow_rules ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for law_tasks
    task_cols = [
        ("task_type", "TEXT DEFAULT 'general'"),
        ("estimated_hours", "REAL DEFAULT 0.0"),
        ("actual_hours", "REAL DEFAULT 0.0"),
        ("is_billable", "INTEGER DEFAULT 0"),
        ("checklist_json", "TEXT"),
        ("completed_at", "TEXT")
    ]
    for col_name, col_type in task_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_tasks ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for law_executions
    exec_cols = [
        ("execution_type", "TEXT DEFAULT 'financial'"),
        ("debtor_name", "TEXT"),
        ("claimed_amount", "REAL DEFAULT 0.0"),
        ("collected_amount", "REAL DEFAULT 0.0"),
        ("decision_number", "TEXT"),
        ("decision_date", "TEXT"),
        ("notes", "TEXT"),
        ("attachment_path", "TEXT")
    ]
    for col_name, col_type in exec_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_executions ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for law_power_of_attorney
    poa_cols = [
        ("agent_name", "TEXT"),
        ("poa_type", "TEXT DEFAULT 'litigation'"),
        ("issuing_authority", "TEXT"),
        ("scope_of_powers", "TEXT"),
        ("status", "TEXT DEFAULT 'active'"),
        ("attachment_path", "TEXT")
    ]
    for col_name, col_type in poa_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_power_of_attorney ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for law_limitations
    lim_cols = [
        ("days_count", "INTEGER"),
        ("action_required", "TEXT"),
        ("alert_days_before", "INTEGER DEFAULT 7"),
        ("law_reference", "TEXT"),
        ("is_critical", "INTEGER DEFAULT 1")
    ]
    for col_name, col_type in lim_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_limitations ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for law_legal_references
    ref_cols = [
        ("category", "TEXT DEFAULT 'regulation'"),
        ("article_number", "TEXT"),
        ("content", "TEXT"),
        ("keywords", "TEXT"),
        ("source", "TEXT")
    ]
    for col_name, col_type in ref_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_legal_references ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for law_expenses
    exp_cols = [
        ("expense_category", "TEXT DEFAULT 'رسوم قضائية'"),
        ("is_billable", "INTEGER DEFAULT 1"),
        ("payment_method", "TEXT DEFAULT 'تحويل بنكي'"),
        ("receipt_path", "TEXT"),
        ("notes", "TEXT")
    ]
    for col_name, col_type in exp_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_expenses ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for law_timesheets
    ts_cols = [
        ("is_billed", "INTEGER DEFAULT 0"),
        ("invoice_id", "INTEGER"),
        ("work_date", "TEXT"),
        ("notes", "TEXT")
    ]
    for col_name, col_type in ts_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_timesheets ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for law_transactions
    trx_cols = [
        ("payment_method", "TEXT DEFAULT 'تحويل بنكي'"),
        ("reference_number", "TEXT"),
        ("client_id", "INTEGER")
    ]
    for col_name, col_type in trx_cols:
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE law_transactions ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass

    # Migrations for invoices
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE invoices ADD COLUMN is_deleted INTEGER DEFAULT 0;"))
    except Exception:
        pass

    # Dynamic Column Synchronization (Ensures PostgreSQL on Railway has all model columns)
    try:
        import sqlalchemy as sa
        insp = sa.inspect(engine)
        existing_tables = set(insp.get_table_names())
        with engine.begin() as conn:
            for t_name, t_obj in Base.metadata.tables.items():
                if t_name in existing_tables:
                    existing_cols = {c['name'] for c in insp.get_columns(t_name)}
                    for col in t_obj.columns:
                        if col.name not in existing_cols:
                            try:
                                col_type_str = col.type.compile(engine.dialect)
                                sql_str = f'ALTER TABLE "{t_name}" ADD COLUMN "{col.name}" {col_type_str}'
                                conn.execute(text(sql_str))
                                print(f"[Migration] Auto-added column {col.name} ({col_type_str}) to table {t_name}")
                            except Exception:
                                pass
    except Exception as sync_exc:
        print(f"[Migration Notice] Auto-sync column check: {sync_exc}")

    # Call cleanup on startup to ensure production keeps only official offices
    try:
        cleanup_and_keep_official_offices()
    except Exception as e:
        print(f"[Startup Cleanup Warning] {e}")

    # Never log DATABASE_URL: it may contain a username and password.
    print(f"[Database] Connected using dialect: {engine.dialect.name}")
    print(f"[Database] Tables initialized successfully.")


def cleanup_and_keep_official_offices(db_session=None):
    """
    بتر وتطهير شامل لقاعدة البيانات للإبقاء فقط على المكاتب الرسمية:
    1. مكتب عبدالله العليمي للمحاماة (ID: 1)
    2. مكتب هشام دغيش للمحاماة (ID: 6 أو المسمى هشام دغيش)
    3. حذف وشطب كافة المكاتب الأخرى نهائياً مع مستخدميها وكافة بياناتها
    4. تصفية القضايا والموكلين والبيانات التجريبية من مكتب 1
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    
    if isinstance(db_session, Session):
        db = db_session
        should_close = False
    else:
        db = SessionLocal()
        should_close = True

    try:
        # 1. تحديث وتثبيت مكتب عبدالله العليمي للمحاماة (ID: 1)
        db.execute(text(
            "UPDATE law_offices SET name = 'مكتب عبدالله العليمي للمحاماة', is_active = 1, "
            "subscription_plan = 'yearly', subscription_end = '2030-01-01 00:00:00' WHERE id = 1"
        ))
        
        # ربط مالك مكتب 1 بحساب ABOOD وتحديث اسمه
        abood = db.execute(text("SELECT id FROM access_profiles WHERE username = 'ABOOD'")).first()
        if abood:
            abood_id = abood[0]
            db.execute(text(
                "UPDATE law_offices SET owner_user_id = :uid WHERE id = 1"
            ), {"uid": abood_id})
            db.execute(text(
                "UPDATE access_profiles SET name = 'عبدالله العليمي (المدير العام)', is_active = 1, "
                "is_superadmin = 1, role = 'مدير', office_id = 1 WHERE id = :uid"
            ), {"uid": abood_id})

        # 2. البحث عن مكتب هشام دغيش أو إنشاءه إن لم يكن موجوداً
        off6 = db.execute(text(
            "SELECT id, name FROM law_offices WHERE id = 6 OR name LIKE '%هشام دغيش%'"
        )).first()
        
        keep_ids = [1]
        if off6:
            off6_id = off6[0]
            keep_ids.append(off6_id)
            db.execute(text(
                "UPDATE law_offices SET name = 'مكتب هشام دغيش للمحاماة', is_active = 1, "
                "subscription_plan = 'yearly', subscription_end = '2030-01-01 00:00:00' WHERE id = :oid"
            ), {"oid": off6_id})
        else:
            db.execute(text(
                "INSERT INTO law_offices (id, name, is_active, status_key, subscription_plan, subscription_end) "
                "VALUES (6, 'مكتب هشام دغيش للمحاماة', 1, 'active', 'yearly', '2030-01-01 00:00:00')"
            ))
            keep_ids.append(6)
            off6_id = 6

        # التأكد من وجود مستخدم لمكتب هشام دغيش
        u6 = db.execute(text("SELECT id FROM access_profiles WHERE office_id = :oid"), {"oid": off6_id}).first()
        if not u6:
            import os, hashlib, base64
            salt = os.urandom(16)
            actual = hashlib.pbkdf2_hmac('sha256', b'admin123456', salt, 260000)
            pin_hash = f"pbkdf2:sha256:260000${base64.b64encode(salt).decode('utf-8').rstrip('=')}${base64.b64encode(actual).decode('utf-8').rstrip('=')}"
            db.execute(text(
                "INSERT INTO access_profiles (office_id, name, username, role, is_active, can_view_all_cases, email, phone, access_pin_hash) "
                "VALUES (:oid, 'المحامي هشام دغيش', 'hesham_dagheish', 'صاحب المكتب', 1, 1, 'hesham@lawfirm.local', '777000001', :pin)"
            ), {"oid": off6_id, "pin": pin_hash})
            u6_new = db.execute(text("SELECT id FROM access_profiles WHERE username = 'hesham_dagheish'")).first()
            if u6_new:
                db.execute(text("UPDATE law_offices SET owner_user_id = :uid WHERE id = :oid"), {"uid": u6_new[0], "oid": off6_id})
        else:
            db.execute(text("UPDATE law_offices SET owner_user_id = :uid WHERE id = :oid"), {"uid": u6[0], "oid": off6_id})

        # 3. جلب كافة المكاتب الأخرى غير 1 وغير مكتب هشام لحذفها وبترها
        del_offices = db.execute(text(
            f"SELECT id FROM law_offices WHERE id NOT IN ({','.join(map(str, keep_ids))}) AND name NOT LIKE '%هشام دغيش%'"
        )).fetchall()
        del_ids = [r[0] for r in del_offices]

        if del_ids:
            del_str = ','.join(map(str, del_ids))
            del_users = db.execute(text(f"SELECT id FROM access_profiles WHERE office_id IN ({del_str})")).fetchall()
            if del_users:
                u_str = ','.join(str(u[0]) for u in del_users)
                db.execute(text(f"DELETE FROM auth_sessions WHERE user_id IN ({u_str})"))
                db.execute(text(f"DELETE FROM access_profiles WHERE id IN ({u_str})"))

            tables = [
                'law_cases', 'law_incoming_cases', 'law_clients', 'law_parties',
                'law_hearings', 'law_tasks', 'law_judgments', 'law_expenses',
                'law_transactions', 'law_power_of_attorney', 'law_documents',
                'law_timesheets', 'law_notes', 'law_correspondences',
                'law_executions', 'law_limitations', 'law_pleadings',
                'payment_requests', 'invoices', 'client_payments',
                'retainer_agreements', 'client_intake_forms', 'law_trust_accounts'
            ]
            for tbl in tables:
                try:
                    db.execute(text(f"DELETE FROM {tbl} WHERE office_id IN ({del_str})"))
                except Exception:
                    pass
            db.execute(text(f"DELETE FROM law_offices WHERE id IN ({del_str})"))
            print(f"[Cleanup] Deleted {len(del_ids)} non-official offices: {del_ids}")

        # 4. تصفية البيانات التجريبية من مكتب 1 (مكتب عبدالله العليمي للمحاماة)
        mock_tables = [
            'law_cases', 'law_incoming_cases', 'law_clients', 'law_parties',
            'law_hearings', 'law_tasks', 'law_judgments', 'law_expenses',
            'law_transactions', 'law_power_of_attorney', 'law_documents',
            'law_timesheets', 'law_notes', 'law_correspondences',
            'law_executions', 'law_limitations', 'law_pleadings',
            'invoices', 'client_payments', 'retainer_agreements',
            'client_intake_forms', 'law_trust_accounts'
        ]
        for tbl in mock_tables:
            try:
                db.execute(text(f"DELETE FROM {tbl} WHERE office_id = 1"))
            except Exception:
                pass

        # حذف المستخدمين التجريبيين من مكتب 1 مع الإبقاء فقط على ABOOD
        mock_u1 = db.execute(text("SELECT id FROM access_profiles WHERE office_id = 1 AND username != 'ABOOD'")).fetchall()
        if mock_u1:
            u1_str = ','.join(str(u[0]) for u in mock_u1)
            db.execute(text(f"DELETE FROM auth_sessions WHERE user_id IN ({u1_str})"))
            db.execute(text(f"DELETE FROM access_profiles WHERE id IN ({u1_str})"))

        db.commit()
        print("[Cleanup] Successfully purged mock data and synchronized official offices (Office 1 & Office 6).")
    except Exception as e:
        db.rollback()
        print(f"[Cleanup Error] {e}")
    finally:
        if should_close:
            db.close()




