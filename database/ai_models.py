"""
AI Chat History, Knowledge, and Quota models — أُعيد إضافتهم بعد حذفهم في init_db()
[BUG-022 FIX] هذه النماذج مطلوبة من ai_assistant.py
"""
from sqlalchemy import Column, Integer, String, Text, Float
from database.database import Base


class AIChatHistory(Base):
    """تاريخ محادثات المساعد الذكي لكل مكتب"""
    __tablename__ = "ai_chat_history"
    id = Column(Integer, primary_key=True, index=True)
    office_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    role = Column(String(20), default="user")  # user | assistant
    content = Column(Text)
    created_at = Column(String(30))
    is_deleted = Column(Integer, default=0)


class AIKnowledge(Base):
    """قاعدة المعرفة المخصصة لكل مكتب"""
    __tablename__ = "ai_knowledge"
    id = Column(Integer, primary_key=True, index=True)
    office_id = Column(Integer, nullable=False, index=True)
    title = Column(String(500))
    content = Column(Text)
    source = Column(String(200))
    created_at = Column(String(30))
    is_deleted = Column(Integer, default=0)


class AIUserQuota(Base):
    """حصة استخدام الذكاء الاصطناعي لكل مستخدم يومياً"""
    __tablename__ = "ai_user_quotas"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    usage_date = Column(String(15))  # YYYY-MM-DD
    requests_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
