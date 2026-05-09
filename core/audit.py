"""
أداة مساعدة لكتابة سجلات التدقيق (Audit Log) في قاعدة البيانات.
تُستخدم لتتبع العمليات الحساسة: إضافة / تعديل / حذف / تسجيل دخول.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import LawAuditLog
from core.logger import app_logger


def write_audit(
    db: Session,
    *,
    table_name: str,
    action_name: str,
    actor_user_id: int | None = None,
    actor_name: str | None = None,
    office_id: int | None = None,
    record_key: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    details: str | None = None,
    session_uuid: str | None = None,
) -> None:
    """
    يكتب سجل تدقيق واحد في الجدول law_audit_log.
    لا يُوقف التطبيق عند الفشل — يسجل الخطأ فقط.
    """
    try:
        import json
        entry = LawAuditLog(
            table_name=table_name,
            action_name=action_name,
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            office_id=office_id,
            record_key=record_key,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values_json=json.dumps(old_values, ensure_ascii=False) if old_values else None,
            new_values_json=json.dumps(new_values, ensure_ascii=False) if new_values else None,
            details=details,
            session_uuid=session_uuid,
            created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        )
        db.add(entry)
        db.flush()  # نحفظ بدون commit لأن الـ caller هو المسؤول عن الـ commit
        app_logger.info(
            f"AUDIT | {action_name} | table={table_name} | "
            f"user={actor_name}({actor_user_id}) | office={office_id} | key={record_key}"
        )
    except Exception as exc:
        app_logger.error(f"write_audit FAILED: {exc}", exc_info=True)
