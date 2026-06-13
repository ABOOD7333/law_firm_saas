"""
API Router للمساعد الذكي القانوني اليمني — الإصدار المتقدم v2.0
يستخدم Gemini كمحرك ذكاء أساسي مع سياق محلي + ذاكرة محادثة
"""
import time
from datetime import datetime
from functools import lru_cache
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import AIChatHistory, AIKnowledge, AccessProfiles
from dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


# ══════════════════════════════════════════════
# Cached Engine Instances (تجنب إعادة الإنشاء)
# ══════════════════════════════════════════════
_intent_detector = None
_search_engine = None
_response_builder = None
_doc_generator = None


def _get_intent_detector():
    global _intent_detector
    if _intent_detector is None:
        from ai_engine.intent_detector import IntentDetector
        _intent_detector = IntentDetector()
    return _intent_detector


def _get_search_engine():
    global _search_engine
    if _search_engine is None:
        from ai_engine.search_engine import LegalSearchEngine
        _search_engine = LegalSearchEngine()
    return _search_engine


def _get_response_builder():
    global _response_builder
    if _response_builder is None:
        from ai_engine.response_builder import ResponseBuilder
        _response_builder = ResponseBuilder()
    return _response_builder


def _get_doc_generator():
    global _doc_generator
    if _doc_generator is None:
        from ai_engine.document_generator import DocumentGenerator
        _doc_generator = DocumentGenerator()
    return _doc_generator


# ══════════════════════════════════════════════
# معالجة الدردشة البسيطة (بدون Gemini)
# ══════════════════════════════════════════════
def _handle_conversational_query(question: str, user_name: str = ""):
    """يعالج الأسئلة العامة والدردشة البسيطة فوراً"""
    import re
    from datetime import datetime, timedelta, timezone

    q = question.strip().lower()
    q = re.sub(r"[أإآ]", "ا", q)
    q = re.sub(r"ى", "ي", q)
    q = re.sub(r"ة", "ه", q)
    q = re.sub(r"[\u064B-\u065F]", "", q)
    q = re.sub(r"[؟\?!،,\.\-\_]", " ", q)
    q = " ".join(q.split())

    # 1. كيف حالك
    wellness_keywords = [
        "كيف حالك", "كيف الحال", "كيفك", "شلونك", "شخبارك", "ايش اخبارك",
        "كيف امورك", "علومك", "ايش علومك", "ايش مسوي",
    ]
    if any(kw in q for kw in wellness_keywords):
        name = user_name if user_name else "عزيزي"
        return f"الحمد لله أنا بخير وعافية، شكراً لسؤالك يا {name}! 😊 كيف يمكنني مساعدتك اليوم؟"

    # 2. التاريخ واليوم
    arabic_weekdays = {0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}
    arabic_months = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}

    utc_now = datetime.now(timezone.utc)
    ast_now = utc_now + timedelta(hours=3)
    weekday_name = arabic_weekdays.get(ast_now.weekday(), "")
    month_name = arabic_months.get(ast_now.month, "")
    date_str = f"{weekday_name}، {ast_now.day} {month_name} {ast_now.year}م"

    date_keywords = ["تاريخ اليوم", "كم تاريخ اليوم", "ما تاريخ اليوم", "ايش تاريخ اليوم", "التاريخ كم", "كم التاريخ"]
    day_keywords = ["ماهو اليوم", "ما هو اليوم", "ايش اليوم", "اليوم ايش"]

    if any(kw in q for kw in date_keywords):
        return f"📅 تاريخ اليوم هو: **{date_str}**"
    if any(kw in q for kw in day_keywords):
        return f"📅 اليوم هو يوم **{weekday_name}**"

    # 3. من أنت
    identity_keywords = ["من انت", "من أنت", "مين انت", "وش انت", "من تكون", "ما عملك", "ما وظيفتك", "من صممك", "من صنعك"]
    if any(kw in q for kw in identity_keywords):
        return (
            "🤖 أنا المساعد الذكي القانوني المتقدم لمنصة **LawSaaS**.\n\n"
            "تم تصميمي بتقنيات الذكاء الاصطناعي المتقدمة لمساعدتك في:\n\n"
            "⚖️ **الاستشارات القانونية** — أجيب على أسئلتك القانونية بدقة مع ذكر المواد والنصوص\n"
            "📊 **تحليل البيانات** — أحلل قضاياك وجلساتك ووضعك المالي بذكاء\n"
            "📄 **صياغة المستندات** — أصوغ العقود والمذكرات والإنذارات بشكل احترافي\n"
            "🔍 **البحث القانوني** — أبحث في القوانين اليمنية وأجد المواد ذات الصلة\n"
            "💡 **الدعم الذكي** — أتذكر محادثتنا وأقدم اقتراحات مفيدة\n\n"
            "كيف يمكنني مساعدتك الآن؟"
        )

    # 4. الشكر
    gratitude_keywords = ["شكرا", "مشكور", "تسلم", "يعطيك العافيه", "يعطيك العافية", "جزاك الله"]
    if any(kw in q for kw in gratitude_keywords) and len(q.split()) <= 4:
        return "العفو! أنا في في الخدمة دائماً 🌸 هل هناك شيء آخر أستطيع مساعدتك فيه؟"

    # 5. التوديع
    farewell_keywords = ["مع السلامه", "مع السلامة", "في امان الله", "باي", "خروج", "وداعا"]
    if any(kw in q for kw in farewell_keywords) and len(q.split()) <= 3:
        return "في أمان الله وحفظه! 👋 أتمنى لك يوماً موفقاً. أنا هنا متى ما احتجت إليّ."

    return None


# ══════════════════════════════════════════════
# نقطة الدخول الرئيسية — /api/ai/chat
# ══════════════════════════════════════════════
@router.post("/chat")
async def ai_chat(request: Request, db: Session = Depends(get_db), current_user: AccessProfiles = Depends(get_current_user)):
    """
    المساعد الذكي المتقدم — يُجيب على أسئلة المستخدم
    باستخدام Gemini AI + سياق محلي + ذاكرة محادثة
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

        if len(question) > 3000:
            return JSONResponse({"success": False, "error": "السؤال طويل جداً (الحد: 3000 حرف)"}, status_code=400)

        # ──────────────────────────────────────
        # 0. الردود المحلية السريعة (تحيات، تاريخ..)
        # ──────────────────────────────────────
        conv_response = _handle_conversational_query(question, user_name)
        if conv_response:
            _save_chat(db, office_id, user_id, question, conv_response, "greeting")
            elapsed = int((time.time() - start_time) * 1000)
            return JSONResponse({
                "success": True,
                "answer": conv_response,
                "intent": "greeting",
                "time_ms": elapsed,
                "suggestions": ["كم عدد القضايا المفتوحة؟", "ما الجلسات القادمة؟", "أنشئ لي عقد إيجار"]
            })

        # ──────────────────────────────────────
        # 1. كشف النية
        # ──────────────────────────────────────
        intent_detector = _get_intent_detector()
        intent = intent_detector.detect(question)

        # ──────────────────────────────────────
        # 2. توليد المستندات القانونية (معالجة خاصة)
        # ──────────────────────────────────────
        if intent.type == "generate_document":
            return await _handle_document_generation(question, intent, db, office_id, user_id, start_time)

        # ──────────────────────────────────────
        # 3. جمع كل السياقات الممكنة
        # ──────────────────────────────────────
        from ai_engine.db_query_engine import DBQueryEngine

        db_engine = DBQueryEngine(
            db, office_id, user_id,
            user_role=getattr(current_user, 'role', 'مدير'),
            can_view_all_cases=getattr(current_user, 'can_view_all_cases', 1)
        )

        # جمع البيانات حسب النية
        db_data = None
        search_results = None
        local_context_parts = []

        # أ. استعلام قاعدة البيانات
        if intent.type in ["query_cases", "query_hearings", "query_clients",
                           "query_finance", "query_tasks", "analyze_stats", "search_case"]:
            try:
                db_data = db_engine.answer_query(intent.type, intent.entities)
            except Exception as e:
                db_data = {"error": str(e)}

        # ب. البحث في القوانين
        if intent.type in ["search_law", "legal_advice", "unknown"]:
            try:
                search_engine = _get_search_engine()
                if intent.law_name and intent.article_number:
                    result = search_engine.search_by_article(intent.law_name, intent.article_number)
                    search_results = [result] if result else []
                else:
                    search_results = search_engine.hybrid_search(question, top_k=5)

                # نتائج المعرفة المخصصة
                custom_results = _search_custom_knowledge(db, office_id, question)
                if custom_results:
                    search_results = (search_results or []) + custom_results
            except Exception:
                search_results = []

        # ج. البحث الموحد (موكلين + قضايا + قوانين)
        unified_results = _unified_assistant_search(db, office_id, question)

        # ──────────────────────────────────────
        # 4. بناء السياق الشامل لـ Gemini
        # ──────────────────────────────────────
        user_context = _build_user_context(current_user, db)
        local_context = _build_local_context(unified_results)
        
        # إضافة نتائج البحث القانوني
        if search_results:
            law_context_parts = []
            for r in search_results[:5]:
                if isinstance(r, dict):
                    law_context_parts.append(
                        f"• {r.get('law', '')} - مادة/عنوان ({r.get('article', '')}) - {r.get('title', '')}:\n  {r.get('text', '')}"
                    )
            if law_context_parts:
                law_text = "مواد قانونية يمنية ذات صلة:\n" + "\n".join(law_context_parts)
                local_context = f"{local_context}\n\n{law_text}" if local_context else law_text

        # دمج كل السياقات
        full_context = "\n\n".join(filter(None, [user_context, local_context]))

        # ──────────────────────────────────────
        # 5. جلب سجل المحادثة من قاعدة البيانات  
        # ──────────────────────────────────────
        _load_conversation_memory(db, office_id, user_id)

        # ──────────────────────────────────────
        # 6. إرسال لـ Gemini مع كامل السياق
        # ──────────────────────────────────────
        answer = _ask_gemini_advanced(
            question=question,
            local_context=full_context,
            user_name=user_name,
            user_id=user_id,
            db_data=db_data,
        )

        # ──────────────────────────────────────
        # 7. Fallback: إذا فشل Gemini
        # ──────────────────────────────────────
        if not answer:
            response_builder = _get_response_builder()
            answer = response_builder.build_response(
                intent_type=intent.type,
                db_data=db_data,
                search_results=search_results,
                entities=intent.entities,
                user_name=user_name
            )

            # إذا كان الرد الافتراضي "لم أتمكن"، استخدم رد الموحد
            if "لم أتمكن من فهم سؤالك" in answer or "لا يمكنني الإجابة" in answer:
                formatted = _format_unified_search_response(unified_results, question)
                if formatted and "عذراً" not in formatted:
                    answer = formatted

        # ──────────────────────────────────────
        # 8. توليد اقتراحات المتابعة
        # ──────────────────────────────────────
        suggestions = _generate_suggestions(intent.type, question)

        # ──────────────────────────────────────
        # 9. حفظ المحادثة
        # ──────────────────────────────────────
        _save_chat(db, office_id, user_id, question, answer, intent.type)

        elapsed = int((time.time() - start_time) * 1000)
        return JSONResponse({
            "success": True,
            "answer": answer,
            "intent": intent.type,
            "time_ms": elapsed,
            "suggestions": suggestions
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": f"حدث خطأ: {str(e)}"
        }, status_code=500)


# ══════════════════════════════════════════════
# معالجة توليد المستندات
# ══════════════════════════════════════════════
async def _handle_document_generation(question, intent, db, office_id, user_id, start_time):
    """معالجة طلبات توليد المستندات القانونية"""
    doc_generator = _get_doc_generator()

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
        form_fields = doc_generator.get_required_fields_with_labels(doc_type)
    else:
        answer = doc_generator.get_documents_menu()

    _save_chat(db, office_id, user_id, question, answer, intent.type)
    elapsed = int((time.time() - start_time) * 1000)
    return JSONResponse({
        "success": True,
        "answer": answer,
        "intent": intent.type,
        "time_ms": elapsed,
        "doc_type": doc_type,
        "form_fields": form_fields,
        "suggestions": ["أنشئ عقد إيجار", "أنشئ مذكرة دفاع", "ما المستندات المتاحة؟"]
    })


@router.post("/generate-document")
async def generate_document(request: Request, db: Session = Depends(get_db), current_user: AccessProfiles = Depends(get_current_user)):
    """توليد مستند قانوني من القالب"""
    try:
        if not current_user:
            return JSONResponse({"success": False, "error": "غير مسجل الدخول"}, status_code=401)

        data = await request.json()
        doc_code = data.get("doc_code", "")
        fields = data.get("fields", {})

        doc_generator = _get_doc_generator()
        success, result = doc_generator.generate(doc_code, fields)

        if success:
            return JSONResponse({
                "success": True,
                "document": result,
                "doc_name": doc_generator.get_document_info(doc_code)["name"] if doc_generator.get_document_info(doc_code) else ""
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

        history = db.query(AIChatHistory).filter(
            AIChatHistory.office_id == current_user.office_id,
            AIChatHistory.user_id == current_user.id,
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
        {"icon": "🔍", "text": "ما إجراءات رفع دعوى استئناف في اليمن؟"},
        {"icon": "📄", "text": "أنشئ لي عقد إيجار"},
        {"icon": "⚠️", "text": "أنشئ إنذاراً قانونياً"},
        {"icon": "🛡️", "text": "أنشئ مذكرة دفاع"},
        {"icon": "📜", "text": "ما المادة 55 من قانون العمل اليمني؟"},
        {"icon": "💡", "text": "ما حقوق العامل في حال الفصل التعسفي؟"},
    ]
    return JSONResponse({"success": True, "suggestions": suggestions})


@router.post("/knowledge/add")
async def add_knowledge(request: Request, db: Session = Depends(get_db), current_user: AccessProfiles = Depends(get_current_user)):
    """إضافة معرفة قانونية مخصصة"""
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
    """عرض قاعدة المعرفة المخصصة"""
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


# ══════════════════════════════════════════════
# الدوال المساعدة الأساسية
# ══════════════════════════════════════════════

def _load_conversation_memory(db: Session, office_id: int, user_id: int):
    """تحميل ذاكرة المحادثة من قاعدة البيانات إلى Gemini"""
    try:
        from ai_engine.llm_service import get_gemini_assistant
        gemini = get_gemini_assistant()
        if not gemini.is_available:
            return

        # تحقق إذا كانت الذاكرة محملة مسبقاً
        existing = gemini._conversation_memory.get(user_id, [])
        if existing:
            return  # الذاكرة موجودة بالفعل

        # جلب آخر 10 محادثات
        history = db.query(AIChatHistory).filter(
            AIChatHistory.office_id == office_id,
            AIChatHistory.user_id == user_id,
            AIChatHistory.is_deleted == 0
        ).order_by(AIChatHistory.created_at.desc()).limit(10).all()

        for h in reversed(history):
            gemini.add_to_memory(user_id, "user", h.question)
            if h.answer:
                gemini.add_to_memory(user_id, "assistant", h.answer)

    except Exception as e:
        print(f"Error loading conversation memory: {e}")


def _ask_gemini_advanced(
    question: str,
    local_context: str = None,
    user_name: str = "",
    user_id: int = None,
    db_data: dict = None,
) -> str:
    """يرسل السؤال لـ Gemini مع السياق الكامل"""
    try:
        from ai_engine.llm_service import get_gemini_assistant
        gemini = get_gemini_assistant()
        if not gemini.is_available:
            return None
        return gemini.ask(
            question=question,
            local_context=local_context,
            user_name=user_name,
            user_id=user_id,
            db_data=db_data,
        )
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


def _build_user_context(current_user, db) -> str:
    """يبني سياق المستخدم الحالي لإرساله مع السؤال لـ Gemini"""
    try:
        role_map = {
            'admin': 'مدير المكتب', 'مدير': 'مدير المكتب',
            'lawyer': 'محامي', 'محامي': 'محامي',
            'secretary': 'سكرتير', 'سكرتير': 'سكرتير',
            'assistant': 'مساعد', 'مساعد': 'مساعد',
            'superadmin': 'مدير النظام العام',
        }
        user_role = getattr(current_user, 'role', 'مستخدم')
        role_arabic = role_map.get(user_role, user_role)

        parts = [
            "--- معلومات المستخدم ---",
            f"الاسم: {current_user.name}",
            f"الصفة: {role_arabic}",
        ]

        if hasattr(current_user, 'office_id') and current_user.office_id:
            try:
                from database.models import LawOffices
                office = db.query(LawOffices).filter(LawOffices.id == current_user.office_id).first()
                if office:
                    parts.append(f"المكتب: {office.name}")
            except Exception:
                pass

        parts.append("--- نهاية معلومات المستخدم ---")
        return "\n".join(parts)
    except Exception:
        return ""


def _build_local_context(unified_results: dict) -> str:
    """يبني نص السياق المحلي من نتائج البحث الموحد"""
    parts = []

    if unified_results.get("clients"):
        parts.append("موكلون مطابقون في النظام:")
        for c in unified_results["clients"]:
            parts.append(f"  - {c['name']} | هاتف: {c['phone']} | قضية: {c.get('case_title', 'لا يوجد')}")

    if unified_results.get("cases"):
        parts.append("قضايا مطابقة:")
        for cs in unified_results["cases"]:
            parts.append(f"  - [{cs.case_number}] {cs.title} | الحالة: {cs.status_key}")

    if unified_results.get("laws"):
        parts.append("مواد قانونية يمنية ذات صلة:")
        for law in unified_results["laws"]:
            parts.append(f"  - {law['law']} مادة/عنوان ({law['article']}) - {law.get('title', '')}:\n    {law['text']}")

    if unified_results.get("custom_knowledge"):
        parts.append("معرفة مخصصة للمكتب:")
        for item in unified_results["custom_knowledge"]:
            parts.append(f"  - {item['article_number']}: {item['article_text'][:200]}")

    return "\n".join(parts) if parts else None


def _generate_suggestions(intent_type: str, question: str) -> list:
    """توليد اقتراحات أسئلة متابعة ذكية"""
    try:
        from ai_engine.llm_service import get_gemini_assistant
        gemini = get_gemini_assistant()
        return gemini.generate_follow_up_suggestions(question, "", intent_type)
    except Exception:
        return ["كم عدد القضايا المفتوحة؟", "ما الجلسات القادمة؟", "أنشئ لي عقد إيجار"]


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
    """بحث موحد في قاعدة البيانات والقوانين"""
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

    words = [w.strip() for w in query_clean.split() if len(w.strip()) > 2]
    stop_words = {"هل", "ما", "من", "عن", "في", "هو", "هي", "اسم", "يكون", "التي", "الذي", "لدينا"}
    search_terms = [w for w in words if w not in stop_words]

    # 1. البحث في الموكلين
    try:
        from database.models import LawClients, LawCases
        all_clients = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.is_deleted == 0
        ).all()

        for c in all_clients:
            c_words = [w for w in c.name.split() if len(w) > 2]
            if not c_words:
                continue
            match_count = sum(1 for cw in c_words if cw in query_clean)
            if match_count >= 2 or (len(c_words) == 1 and c.name in query_clean):
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
    except Exception:
        pass

    # 2. البحث في القضايا
    try:
        from database.models import LawCases
        all_cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        ).all()

        for case in all_cases:
            if case.case_number in query_clean:
                results["cases"].append(case)
                continue
            case_words = [w for w in case.title.split() if len(w) > 2]
            if not case_words:
                continue
            match_count = sum(1 for cw in case_words if cw in query_clean)
            if match_count >= 2:
                results["cases"].append(case)
    except Exception:
        pass

    # 3. البحث في القوانين
    try:
        search_engine = _get_search_engine()
        law_matches = search_engine.hybrid_search(query_clean, top_k=3)
        results["laws"] = [m for m in law_matches if m.get("score", 0) > 0.1]
    except Exception:
        pass

    # 4. المعرفة المخصصة
    try:
        custom_matches = _search_custom_knowledge(db, office_id, query_clean)
        results["custom_knowledge"] = custom_matches
    except Exception:
        pass

    # 5. بحث RAG
    try:
        from rag_engine.core.vector_store import vector_store
        if vector_store.collection.count() > 0:
            rag_matches = vector_store.semantic_search(query_clean, n_results=2)
            results["semantic"] = rag_matches
    except Exception:
        pass

    return results


def _format_unified_search_response(results: dict, query: str) -> str:
    """يبني رداً نصياً منسقاً يدمج نتائج البحث الموحد"""
    lines = []

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

    if results["laws"]:
        yemeni_laws = [l for l in results["laws"] if l.get("category") != "إرشاد النظام"]
        system_guides = [l for l in results["laws"] if l.get("category") == "إرشاد النظام"]

        if yemeni_laws:
            lines.append("⚖️ **المواد القانونية المرتبطة في القانون اليمني:**")
            lines.append("─────────────────────────")
            for i, law in enumerate(yemeni_laws, 1):
                lines.append(f"**{i}. {law['law']} - مادة ({law['article']})**")
                if law.get("title"):
                    lines.append(f"   📌 *{law['title']}*")
                lines.append(f"   📜 {law['text']}")
                lines.append("")

        if system_guides:
            lines.append("💻 **دليل استخدام وتشغيل المنصة:**")
            lines.append("─────────────────────────")
            for i, guide in enumerate(system_guides, 1):
                lines.append(f"**{i}. {guide['title']}**")
                lines.append(f"   📜 {guide['text']}")
                lines.append("")

    if results["custom_knowledge"]:
        lines.append("📖 **من دليل إجراءات ومعرفة المكتب المخصصة:**")
        lines.append("─────────────────────────")
        for i, item in enumerate(results["custom_knowledge"], 1):
            lines.append(f"**{i}. {item['law_name']} - {item['article_number']}**")
            lines.append(f"   📜 {item['article_text']}")
            lines.append("")

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
            "عذراً، أنا مساعد قانوني مخصص للقوانين والتشريعات اليمنية وإدارة مكتب المحاماة فقط. "
            "لا يمكنني الإجابة على الأسئلة العامة أو الخارجة عن هذا النطاق."
        )

    return "\n".join(lines)
