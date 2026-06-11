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
            "db": DBQueryEngine(
                db, 
                user.office_id, 
                user.id, 
                user_role=getattr(user, 'role', 'مدير'), 
                can_view_all_cases=getattr(user, 'can_view_all_cases', 1)
            ),
            "response": ResponseBuilder(),
            "docs": DocumentGenerator(),
        }
    except Exception as e:
        return None


@router.post("/chat")
async def ai_chat(request: Request, db: Session = Depends(get_db), current_user: AccessProfiles = Depends(get_current_user)):
    """
    المساعد الذكي - يُجيب على أسئلة المستخدم
    """
    start_time = time.time()
    try:
        if not current_user:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        user_id = current_user.id
        office_id = current_user.office_id
        user_name = current_user.name

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
            db_engine = DBQueryEngine(
                db, 
                office_id, 
                user_id, 
                user_role=getattr(current_user, 'role', 'مدير'), 
                can_view_all_cases=getattr(current_user, 'can_view_all_cases', 1)
            )
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

        # أ. إذا كانت النية استعلام عن موكل
        # نقوم بالاستعلام، وإذا لم نجد نتائج بالاسم الدقيق أو لم يستخرج بالـ Regex،
        # نستخدم البحث الموحد لمطابقة اسم الموكل دلالياً/بالأجزاء
        if intent.type == "query_clients":
            if "client_name" in intent.entities:
                try:
                    db_data = db_engine.answer_query(intent.type, intent.entities)
                except Exception as e:
                    db_data = {"error": str(e)}

            if not db_data or not db_data.get("success") or not db_data.get("data"):
                unified_results = _unified_assistant_search(db, office_id, question)
                if unified_results["clients"]:
                    answer = _format_unified_search_response(unified_results, question)
                    _save_chat(db, office_id, user_id, question, answer, intent.type)
                    elapsed = int((time.time() - start_time) * 1000)
                    return JSONResponse({
                        "success": True,
                        "answer": answer,
                        "intent": intent.type,
                        "time_ms": elapsed
                    })

        # ب. إذا كانت النية استشارة عامة أو غير معروفة، نستخدم البحث الموحد الذكي مباشرة
        if intent.type in ["unknown", "legal_advice"]:
            unified_results = _unified_assistant_search(db, office_id, question)
            answer = _format_unified_search_response(unified_results, question)
            _save_chat(db, office_id, user_id, question, answer, intent.type)
            elapsed = int((time.time() - start_time) * 1000)
            return JSONResponse({
                "success": True,
                "answer": answer,
                "intent": intent.type,
                "time_ms": elapsed
            })

        if intent.type in ["query_cases", "query_hearings", "query_clients",
                            "query_finance", "query_tasks", "analyze_stats",
                            "search_case"]:
            # استعلام قاعدة البيانات (إذا لم نكن قد قمنا بالاستعلام بالفعل)
            if not (intent.type == "query_clients" and db_data is not None):
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
            doc_type = None
            detected = doc_generator.detect_document_type(question)
            if detected and doc_generator.get_document_info(detected):
                doc_type = detected
            
            if not doc_type and intent.document_type:
                if doc_generator.get_document_info(intent.document_type):
                    doc_type = intent.document_type

            form_fields = None
            if doc_type:
                fields_msg = doc_generator.get_fields_questions(doc_type)
                info = doc_generator.get_document_info(doc_type)
                doc_name = info["name"] if info else "المستند"
                answer = f"📄 سأُنشئ لك **{doc_name}**\n\n{fields_msg}"
                # جلب أسماء الحقول ومسمياتها لعرض النموذج التفاعلي
                form_fields = doc_generator.get_required_fields_with_labels(doc_type)
            else:
                answer = doc_generator.get_documents_menu()

            # حفظ المحادثة
            _save_chat(db, office_id, user_id, question, answer, intent.type)
            elapsed = int((time.time() - start_time) * 1000)
            return JSONResponse({
                "success": True, 
                "answer": answer,
                "intent": intent.type, 
                "time_ms": elapsed,
                "doc_type": doc_type,
                "form_fields": form_fields
            })

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
async def generate_document(request: Request, db: Session = Depends(get_db), current_user: AccessProfiles = Depends(get_current_user)):
    """توليد مستند قانوني من القالب"""
    try:
        if not current_user:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

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
async def get_chat_history(request: Request, db: Session = Depends(get_db), current_user: AccessProfiles = Depends(get_current_user)):
    """جلب سجل المحادثات"""
    try:
        if not current_user:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        user_id = current_user.id
        office_id = current_user.office_id

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
async def add_knowledge(request: Request, db: Session = Depends(get_db), current_user: AccessProfiles = Depends(get_current_user)):
    """إضافة معرفة قانونية مخصصة (أحكام، تعاميم، ...)"""
    try:
        if not current_user:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        data = await request.json()
        knowledge = AIKnowledge(
            office_id=current_user.office_id,
            created_by=current_user.id,
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
async def list_knowledge(request: Request, db: Session = Depends(get_db), current_user: AccessProfiles = Depends(get_current_user)):
    """عرض قاعدة المعرفة المخصصة للمكتب"""
    try:
        if not current_user:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        items = db.query(AIKnowledge).filter(
            AIKnowledge.office_id == current_user.office_id,
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


def _unified_assistant_search(db: Session, office_id: int, query_text: str) -> dict:
    """
    يقوم بالبحث الموحد في قاعدة البيانات والقوانين
    لإيجاد أي موكلين أو قضايا أو نصوص قانونية مطابقة
    """
    results = {
        "clients": [],
        "cases": [],
        "laws": [],
        "custom_knowledge": [],
        "semantic": []
    }
    
    query_clean = query_text.strip()
    if not query_clean:
        return results
        
    # تطبيع الكلمات للبحث
    words = [w.strip() for w in query_clean.split() if len(w.strip()) > 2]
    # إزالة الكلمات الشائعة (stop words)
    stop_words = {"هل", "ما", "من", "عن", "في", "هو", "هي", "اسم", "يكون", "التي", "الذي", "لدينا", "هوية", "هاتف", "رقم"}
    search_terms = [w for w in words if w not in stop_words]
    
    # 1. البحث في الموكلين
    try:
        from database.models import LawClients, LawCases
        # جلب جميع موكلي المكتب (العدد عادة محدود وسهل الفحص)
        all_clients = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.is_deleted == 0
        ).all()
        
        for c in all_clients:
            # التحقق من تطابق الاسم مع نص السؤال
            # إذا كان اسم الموكل بالكامل أو جزء كبير منه موجود في نص السؤال
            c_words = [w for w in c.name.split() if len(w) > 2]
            if not c_words:
                continue
            
            # تطابق كلمتين على الأقل أو الاسم كامل
            match_count = sum(1 for cw in c_words if cw in query_clean)
            if match_count >= 2 or (len(c_words) == 1 and c.name in query_clean):
                # جلب القضية المرتبطة
                case_title = "لا يوجد"
                if c.case_id:
                    case_rec = db.query(LawCases).filter(LawCases.id == c.case_id).first()
                    if case_rec:
                        case_title = f"{case_rec.title} ({case_rec.case_number})"
                        
                results["clients"].append({
                    "id": c.id,
                    "name": c.name,
                    "phone": c.phone or "غير مسجل",
                    "email": c.email or "غير مسجل",
                    "national_id": c.national_id or "غير مسجل",
                    "case_title": case_title,
                    "case_number": c.case_number or "غير مسجل"
                })
    except Exception as e:
        print(f"Error in unified client search: {e}")
        
    # 2. البحث في القضايا
    try:
        from database.models import LawCases
        all_cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        ).all()
        
        for case in all_cases:
            # التحقق من وجود رقم القضية أو العنوان في السؤال
            if case.case_number in query_clean:
                results["cases"].append(case)
                continue
            
            case_words = [w for w in case.title.split() if len(w) > 2]
            if not case_words:
                continue
            match_count = sum(1 for cw in case_words if cw in query_clean)
            if match_count >= 2:
                results["cases"].append(case)
    except Exception as e:
        print(f"Error in unified case search: {e}")
        
    # 3. البحث في القوانين اليمنية (BM25)
    try:
        from ai_engine.search_engine import LegalSearchEngine
        se = LegalSearchEngine()
        law_matches = se.search(query_clean, top_k=3)
        # الاحتفاظ فقط بالمواد ذات الجودة
        results["laws"] = [m for m in law_matches if m.get("score", 0) > 0.1]
    except Exception as e:
        print(f"Error in unified law search: {e}")
        
    # 4. البحث في المعرفة المخصصة للمكتب
    try:
        custom_matches = _search_custom_knowledge(db, office_id, query_clean)
        results["custom_knowledge"] = custom_matches
    except Exception as e:
        print(f"Error in unified custom knowledge search: {e}")
        
    # 5. البحث في RAG المتجهات (ChromaDB)
    try:
        from rag_engine.core.vector_store import vector_store
        # نبحث فقط إذا كان chromadb منصب ولديه وثائق
        if vector_store.collection.count() > 0:
            rag_matches = vector_store.semantic_search(query_clean, n_results=2)
            results["semantic"] = rag_matches
    except Exception:
        pass
        
    return results


def _format_unified_search_response(results: dict, query: str) -> str:
    """يبني رداً نصياً منسقاً يدمج نتائج البحث الموحد"""
    lines = []
    
    # 1. الموكلون المطابقون
    if results["clients"]:
        lines.append("👤 **معلومات الموكل(ة) المطابق في النظام:**")
        lines.append("─────────────────────────")
        for c in results["clients"]:
            lines.append(f"• **الاسم:** {c['name']}")
            lines.append(f"  📞 **الهاتف:** {c['phone']}")
            lines.append(f"  📧 **البريد:** {c['email']}")
            lines.append(f"  🆔 **الهوية:** {c['national_id']}")
            lines.append(f"  📁 **القضية المرتبطة:** {c['case_title']}")
            lines.append("")
            
    # 2. القضايا المطابقة
    if results["cases"]:
        lines.append("📂 **القضايا المطابقة في النظام:**")
        lines.append("─────────────────────────")
        for cs in results["cases"]:
            status_labels = {"open": "مفتوحة", "active": "نشطة", "closed": "مغلقة", "completed": "مكتملة", "draft": "مسودة"}
            status_str = status_labels.get(cs.status_key, cs.status_key)
            lines.append(f"• **[{cs.case_number}]** {cs.title} | الحالة: *{status_str}*")
            if cs.summary:
                lines.append(f"  *ملخص:* {cs.summary[:150]}")
            lines.append("")
            
    # 3. القوانين اليمنية المطابقة
    if results["laws"]:
        lines.append("⚖️ **المواد القانونية المرتبطة في القانون اليمني:**")
        lines.append("─────────────────────────")
        for i, law in enumerate(results["laws"], 1):
            lines.append(f"**{i}. {law['law']} - مادة ({law['article']})**")
            if law.get("title"):
                lines.append(f"   📌 *{law['title']}*")
            lines.append(f"   📜 {law['text']}")
            lines.append("")
            
    # 4. المعرفة المخصصة للمكتب
    if results["custom_knowledge"]:
        lines.append("📖 **من دليل إجراءات ومعرفة المكتب المخصصة:**")
        lines.append("─────────────────────────")
        for i, item in enumerate(results["custom_knowledge"], 1):
            lines.append(f"**{i}. {item['law_name']} - {item['article_number']}**")
            lines.append(f"   📜 {item['article_text']}")
            lines.append("")
            
    # 5. سياق RAG الدلالي
    if results["semantic"]:
        lines.append("📚 **نصوص إضافية مستخرجة دلالياً من قاعدة المعرفة:**")
        lines.append("─────────────────────────")
        for i, doc in enumerate(results["semantic"], 1):
            text = doc["text"]
            meta = doc.get("metadata", {})
            file_name = meta.get("file_name", "مستند معرفي")
            lines.append(f"**{i}. مقتبس من [{file_name}]:**")
            lines.append(f"   📜 {text[:300]}...")
            lines.append("")
            
    if not lines:
        return (
            "🤔 لم أتمكن من فهم سؤالك بشكل كامل أو العثور على بيانات مطابقة له في النظام أو القوانين.\n\n"
            "💡 **جرّب أحد هذه الأوامر:**\n"
            "• كم عدد القضايا المفتوحة؟\n"
            "• ما جلسات اليوم؟\n"
            "• المادة 55 من قانون العمل\n"
            "• صياغة عقد إيجار\n"
            "• المهام المعلقة"
        )
        
    return "\n".join(lines)
