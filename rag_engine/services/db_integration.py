"""
Database Integration Service
يربط المساعد الذكي RAG بقاعدة بيانات المنصة الحقيقية (PostgreSQL/SQLite)
للإجابة على أسئلة مثل: الجلسات القادمة، القضايا المفتوحة، إلخ.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta

# استيراد النماذج (نعتمد على أنه سيتم تمرير الجلسة Session من الـ router)
from database.models import Cases, Clients, Hearings, Tasks

class DBIntegrationService:
    
    @staticmethod
    def get_open_cases_count(db: Session, office_id: int) -> str:
        """كم عدد القضايا المفتوحة؟"""
        count = db.query(Cases).filter(
            Cases.office_id == office_id, 
            Cases.is_deleted == 0,
            Cases.status.in_(['مفتوحة', 'قيد الترافع', 'منظورة', 'نشطة']) # تقريب للحالات المفتوحة
        ).count()
        return f"عدد القضايا المفتوحة حالياً في المكتب هو: {count} قضية."

    @staticmethod
    def get_upcoming_hearings(db: Session, office_id: int, days: int = 7) -> str:
        """ما الجلسات القادمة؟"""
        today = date.today()
        end_date = today + timedelta(days=days)
        
        hearings = db.query(Hearings).filter(
            Hearings.office_id == office_id,
            Hearings.is_deleted == 0,
            Hearings.hearing_date >= today.isoformat(),
            Hearings.hearing_date <= end_date.isoformat()
        ).order_by(Hearings.hearing_date).all()
        
        if not hearings:
            return f"ليس لديك أي جلسات مجدولة خلال الـ {days} أيام القادمة."
            
        result = [f"لديك {len(hearings)} جلسات خلال الـ {days} أيام القادمة:\n"]
        for h in hearings:
            # افتراض وجود case_id أو ما شابه
            result.append(f"- بتاريخ {h.hearing_date} الساعة {h.hearing_time}: {h.title}")
            
        return "\n".join(result)

    @staticmethod
    def get_pending_tasks(db: Session, office_id: int, user_id: int = None) -> str:
        """ما المهام المعلقة؟"""
        query = db.query(Tasks).filter(
            Tasks.office_id == office_id,
            Tasks.is_deleted == 0,
            Tasks.status != 'مكتملة'
        )
        if user_id:
            query = query.filter(Tasks.assigned_to == user_id)
            
        tasks = query.order_by(Tasks.due_date).limit(5).all()
        
        if not tasks:
            return "ليس لديك أي مهام معلقة! أداء ممتاز."
            
        result = [f"المهام المعلقة (أهم 5):"]
        for t in tasks:
            result.append(f"- {t.title} (مستحقة في {t.due_date})")
            
        return "\n".join(result)

db_integration = DBIntegrationService()
