"""
Database Integration Service
يربط المساعد الذكي RAG بقاعدة بيانات المنصة الحقيقية (PostgreSQL/SQLite)
للإجابة على أسئلة مثل: الجلسات القادمة، القضايا المفتوحة، إلخ.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta

# استيراد النماذج الحقيقية للمكتب
from database.models import LawCases, LawClients, LawHearings, LawTasks

class DBIntegrationService:
    
    @staticmethod
    def get_open_cases_count(db: Session, office_id: int) -> str:
        """كم عدد القضايا المفتوحة؟"""
        count = db.query(LawCases).filter(
            LawCases.office_id == office_id, 
            LawCases.is_deleted == 0,
            LawCases.status_key.notin_(['closed', 'مغلقة'])
        ).count()
        return f"عدد القضايا المفتوحة حالياً في المكتب هو: {count} قضية."

    @staticmethod
    def get_upcoming_hearings(db: Session, office_id: int, days: int = 7) -> str:
        """ما الجلسات القادمة؟"""
        today = date.today()
        end_date = today + timedelta(days=days)
        
        hearings = db.query(LawHearings).filter(
            LawHearings.office_id == office_id,
            LawHearings.is_deleted == 0,
            LawHearings.hearing_at >= today.isoformat(),
            LawHearings.hearing_at <= end_date.isoformat() + " 23:59:59"
        ).order_by(LawHearings.hearing_at).all()
        
        if not hearings:
            return f"ليس لديك أي جلسات مجدولة خلال الـ {days} أيام القادمة."
            
        result = [f"لديك {len(hearings)} جلسات خلال الـ {days} أيام القادمة:\n"]
        for h in hearings:
            result.append(f"- بتاريخ {h.hearing_at}: {h.title}")
            
        return "\n".join(result)

    @staticmethod
    def get_pending_tasks(db: Session, office_id: int, user_id: int = None) -> str:
        """ما المهام المعلقة؟"""
        query = db.query(LawTasks).filter(
            LawTasks.office_id == office_id,
            LawTasks.is_deleted == 0,
            LawTasks.status_key.notin_(['completed', 'مكتملة'])
        )
        if user_id:
            query = query.filter(LawTasks.assignee_user_id == user_id)
            
        tasks = query.order_by(LawTasks.due_at).limit(5).all()
        
        if not tasks:
            return "ليس لديك أي مهام معلقة! أداء ممتاز."
            
        result = [f"المهام المعلقة (أهم 5):"]
        for t in tasks:
            result.append(f"- {t.title} (مستحقة في {t.due_at})")
            
        return "\n".join(result)

db_integration = DBIntegrationService()
