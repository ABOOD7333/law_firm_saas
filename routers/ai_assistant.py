"""
API Router للمساعد الذكي القانوني اليمني
يربط الواجهة بمحرك الذكاء والقوانين اليمنية
"""
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import AIChatHistory, AIKnowledge, AccessProfiles
from dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


def _get_ai_engine(db: Session, user):
    """يُنشئ محرك الذكاء مع إعدادات المستخدم"""
    try:
        from ai_engine.intent_detector import IntentDetector
        from ai_engine.search_engine import LegalSearchEngine
        from ai_engine.db_query_engine import DBQueryEngine
        from ai_engine.response_builder import ResponseBuilder
        from ai_engine.document_generator import DocumentGenerator

        return {
            "intent": IntentDetector(),
            "search": LegalSearchEngine(),
            "db": DBQueryEngine(db, user.office_id, user.id),
            "response": ResponseBuilder(),
            "docs": DocumentGenerator(),
        }
    except Exception as e:
        return None


@router.post("/chat")
async def ai_chat(request: Request, db: Session = Depends(get_db)):
    """
    المساعد الذكي - يُجيب على أسئلة المستخدم
    """
    start_time = time.time()
    try:
        # التحقق من الجلسة
        session_token = request.cookies.get("session_token")
        if not session_token:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        from main import _active_sessions
        session = _active_sessions.get(session_token)
        if not session:
            return JSONResponse({"success": False, "error": "الجلسة منتهية"}, status_code=401)

        user_id = session.get("user_id")
        office_id = session.get("office_id")
        user_name = session.get("name", "")

        data = await request.json()
        question = (data.get("question") or data.get("message") or "").strip()

        if not question:
            return JSONResponse({"success": False, "error": "السؤال فارغ"}, status_code=400)

        # الحد الأقصى لطول السؤال
        if len(question) > 2000:
            return JSONResponse({"success": False, "error": "السؤال طويل جداً"}, status_code=400)

        # تحميل المحركات
        try:
            from ai_engine.intent_detector import IntentDetector
            from ai_engine.search_engine import LegalSearchEngine
            from ai_engine.db_query_engine import DBQueryEngine
            from ai_engine.response_builder import ResponseBuilder
            from ai_engine.document_generator import DocumentGenerator

            intent_detector = IntentDetector()
            search_engine = LegalSearchEngine()
            db_engine = DBQueryEngine(db, office_id, user_id)
            response_builder = ResponseBuilder()
            doc_generator = DocumentGenerator()

        except Exception as e:
            return JSONResponse({
                "success": True,
                "answer": f"⚠️ المساعد الذكي لا يزال يُحمَّل. يرجى المحاولة مرة أخرى.\nالخطأ التقني: {str(e)}"
            })

        # 1. كشف النية
        intent = intent_detector.detect(question)

        # 2. تنفيذ بناءً على النية
        db_data = None
        search_results = None

        if intent.type in ["query_cases", "query_hearings", "query_clients",
                            "query_finance", "query_tasks", "analyze_stats",
                            "search_case"]:
            # استعلام قاعدة البيانات
            try:
                db_data = db_engine.answer_query(intent.type, intent.entities)
            except Exception as e:
                db_data = {"error": str(e)}

        elif intent.type == "search_law":
            # البحث في القوانين اليمنية
            try:
                if intent.law_name and intent.article_number:
                    result = search_engine.search_by_article(
                        intent.law_name, intent.article_number
                    )
                    search_results = [result] if result else []
                else:
                    search_results = search_engine.search(question, top_k=5)

                # إضافة نتائج قاعدة المعرفة المخصصة
                custom_results = _search_custom_knowledge(db, office_id, question)
                if custom_results:
                    search_results = (search_results or []) + custom_results
            except Exception as e:
                search_results = []

        elif intent.type == "generate_document":
            # توليد مستند
            doc_type = intent.document_type or doc_generator.detect_document_type(question)
            if doc_type:
                fields_msg = doc_generator.get_fields_questions(doc_type)
                answer = f"📄 سأُنشئ لك **{doc_generator.get_document_info(doc_type)['name']}**\n\n{fields_msg}"
            else:
                answer = doc_generator.get_documents_menu()

            # حفظ المحادثة
            _save_chat(db, office_id, user_id, question, answer, intent.type)
            elapsed = int((time.time() - start_time) * 1000)
            return JSONResponse({"success": True, "answer": answer,
                                  "intent": intent.type, "time_ms": elapsed})

        # 3. بناء الرد
        answer = response_builder.build_response(
            intent_type=intent.type,
            db_data=db_data,
            search_results=search_results,
            entities=intent.entities,
            user_name=user_name
        )

        # 4. حفظ المحادثة
        elapsed = int((time.time() - start_time) * 1000)
        _save_chat(db, office_id, user_id, question, answer, intent.type)

        return JSONResponse({
            "success": True,
            "answer": answer,
            "intent": intent.type,
            "time_ms": elapsed
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": f"حدث خطأ: {str(e)}"
        }, status_code=500)


@router.post("/generate-document")
async def generate_document(request: Request, db: Session = Depends(get_db)):
    """توليد مستند قانوني من القالب"""
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        from main import _active_sessions
        session = _active_sessions.get(session_token)
        if not session:
            return JSONResponse({"success": False, "error": "الجلسة منتهية"}, status_code=401)

        data = await request.json()
        doc_code = data.get("doc_code", "")
        fields = data.get("fields", {})

        from ai_engine.document_generator import DocumentGenerator
        generator = DocumentGenerator()

        success, result = generator.generate(doc_code, fields)

        if success:
            return JSONResponse({
                "success": True,
                "document": result,
                "doc_name": generator.get_document_info(doc_code)["name"] if generator.get_document_info(doc_code) else ""
            })
        else:
            return JSONResponse({"success": False, "error": result}, status_code=400)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/history")
async def get_chat_history(request: Request, db: Session = Depends(get_db)):
    """جلب سجل المحادثات"""
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        from main import _active_sessions
        session = _active_sessions.get(session_token)
        if not session:
            return JSONResponse({"success": False, "error": "الجلسة منتهية"}, status_code=401)

        user_id = session.get("user_id")
        office_id = session.get("office_id")

        history = db.query(AIChatHistory).filter(
            AIChatHistory.office_id == office_id,
            AIChatHistory.user_id == user_id,
            AIChatHistory.is_deleted == 0
        ).order_by(AIChatHistory.created_at.desc()).limit(50).all()

        return JSONResponse({
            "success": True,
            "history": [
                {
                    "id": h.id,
                    "question": h.question,
                    "answer": h.answer,
                    "intent": h.intent_type,
                    "created_at": h.created_at
                } for h in reversed(history)
            ]
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/suggestions")
async def get_suggestions(request: Request):
    """اقتراحات أسئلة للمستخدم"""
    suggestions = [
        {"icon": "⚖️", "text": "كم عدد القضايا المفتوحة هذا الشهر؟"},
        {"icon": "📅", "text": "ما الجلسات المقررة غداً؟"},
        {"icon": "👥", "text": "كم عدد الموكلين النشطين؟"},
        {"icon": "💰", "text": "ما إجمالي الإيرادات هذا الشهر؟"},
        {"icon": "📋", "text": "ما المهام المعلقة اليوم؟"},
        {"icon": "📊", "text": "ما نسبة نجاح القضايا هذا العام؟"},
        {"icon": "🔍", "text": "ما المادة 100 من القانون المدني اليمني؟"},
        {"icon": "📄", "text": "أنشئ لي عقد إيجار"},
        {"icon": "⚠️", "text": "أنشئ إنذاراً قانونياً"},
        {"icon": "🛡️", "text": "أنشئ مذكرة دفاع"},
        {"icon": "🔎", "text": "ابحث عن القضايا المتعلقة بالعقارات"},
        {"icon": "📜", "text": "ما إجراءات رفع الاستئناف في اليمن؟"},
    ]
    return JSONResponse({"success": True, "suggestions": suggestions})


@router.post("/knowledge/add")
async def add_knowledge(request: Request, db: Session = Depends(get_db)):
    """إضافة معرفة قانونية مخصصة (أحكام، تعاميم، ...)"""
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        from main import _active_sessions
        session = _active_sessions.get(session_token)
        if not session:
            return JSONResponse({"success": False, "error": "الجلسة منتهية"}, status_code=401)

        data = await request.json()
        knowledge = AIKnowledge(
            office_id=session["office_id"],
            created_by=session["user_id"],
            category=data.get("category", "أخرى"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            keywords=data.get("keywords", ""),
            source=data.get("source", ""),
        )
        db.add(knowledge)
        db.commit()
        return JSONResponse({"success": True, "message": "تمت إضافة المعرفة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/knowledge/list")
async def list_knowledge(request: Request, db: Session = Depends(get_db)):
    """عرض قاعدة المعرفة المخصصة للمكتب"""
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        from main import _active_sessions
        session = _active_sessions.get(session_token)
        if not session:
            return JSONResponse({"success": False, "error": "الجلسة منتهية"}, status_code=401)

        items = db.query(AIKnowledge).filter(
            AIKnowledge.office_id == session["office_id"],
            AIKnowledge.is_deleted == 0
        ).order_by(AIKnowledge.created_at.desc()).all()

        return JSONResponse({
            "success": True,
            "knowledge": [
                {
                    "id": k.id,
                    "category": k.category,
                    "title": k.title,
                    "content": k.content[:200] + "..." if len(k.content) > 200 else k.content,
                    "source": k.source,
                    "created_at": k.created_at
                } for k in items
            ]
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ==============================
# دوال مساعدة
# ==============================

def _save_chat(db: Session, office_id: int, user_id: int,
               question: str, answer: str, intent_type: str):
    """يحفظ المحادثة في قاعدة البيانات"""
    try:
        chat = AIChatHistory(
            office_id=office_id,
            user_id=user_id,
            question=question,
            answer=answer,
            intent_type=intent_type,
        )
        db.add(chat)
        db.commit()
    except Exception:
        db.rollback()


def _search_custom_knowledge(db: Session, office_id: int, query: str):
    """يبحث في قاعدة المعرفة المخصصة للمكتب"""
    try:
        keywords = query.split()
        results = []
        items = db.query(AIKnowledge).filter(
            AIKnowledge.office_id == office_id,
            AIKnowledge.is_deleted == 0
        ).all()

        for item in items:
            score = 0
            content_lower = (item.content + " " + item.title).lower()
            for kw in keywords:
                if kw.lower() in content_lower:
                    score += 1
            if score > 0:
                results.append({
                    "law_name": item.category,
                    "article_number": item.title,
                    "article_text": item.content,
                    "source": item.source or "قاعدة المعرفة المخصصة",
                    "score": score / len(keywords)
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:3]
    except Exception:
        return []
